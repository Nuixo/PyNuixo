import os
import sys
from dataclasses import dataclass
from enum import Enum
import unicodedata
import pickle
from getpass import getpass

import requests
from bs4 import BeautifulSoup

# BASE_URL = "https://secure.nnn.ed.jp/mypage/"
# loginURL = "https://secure.nnn.ed.jp/mypage/login"
# scoreURL = "https://secure.nnn.ed.jp/mypage/result/pc/list/index"
# #reauthprepareURL = "https://secure.nnn.ed.jp/mypage/reauth_login/prepare?url=/result/pc/list/index"
# reauthtokenURL = "https://secure.nnn.ed.jp/mypage/reauth_login/index?url=/result/pc/list/index"
# #reauthloginURL = "https://secure.nnn.ed.jp/mypage/reauth_login/index?url=/result/pc/list/index"
# reauthURL = "https://secure.nnn.ed.jp/mypage/reauth_login/login"

header = {
    'User-Agent': 'PyNuixo'
}


def split_list(l, n):
    """
    Listを分割
    :param l: List
    :param n: 分割数
    :return: 
    """
    for idx in range(0, len(l), n):
        yield l[idx:idx + n]


class MyPageURLs(Enum):
    TOKEN_PATH = "/mypage/"
    LOGIN_PATH = "/mypage/login"
    REAUTH_TOKEN_PATH = "/mypage/reauth_login/index?url=/result/pc/list/index"
    REAUTH_PATH = "/mypage/reauth_login/login"
    SCORE_PATH = "/mypage/result/pc/list/index"
    RESET_PASS_PATH = "/mypage/password_reminder/input"

    def get_url(self, school) -> str:
        return school.get_base_url() + self.value


@dataclass
class SubjectScore:
    subject: str
    limit: str
    percentage: int
    score: str


class LoginState(Enum):
    SUCCESS = "成功"
    WRONG_ACCOUNT = "学籍番号またはパスワードが違います"
    NOT_ENTERED = "ログインIDまたはパスワードに未入力項目があります。"
    PASS_RESET = "パスワードのリセットを行ってください"
    REAUTH_FAILED = "再認証失敗"
    NETWORK_ERROR = "ネットワークエラー"
    CANT_USE = "マイページを使用することはできません"


class School(Enum):
    N = "https://secure.nnn.ed.jp"
    S = "https://s-secure.nnn.ed.jp"

    def get_base_url(self):
        return self.value


class PyNuixo:
    def __init__(self, username, password):
        self.username = username
        self.password = password

        self.cookie_path = "cookies.pkl"
        self.session = requests.Session()

        if os.path.exists(self.cookie_path):
            self.__load_cookies(self.session)

        self.school = self.__username2school(self.username)


    def login(self) -> LoginState:
        res = self.session.get(MyPageURLs.TOKEN_PATH.get_url(self.school))
        soup = BeautifulSoup(res.text, "html.parser")
        token = soup.find(attrs={'name': '_token'}).get('value')

        data = {
            'loginId': self.username,
            'password': self.password,
            'url': '/result/pc/list/index',
            '_token': token
        }

        response = self.session.post(MyPageURLs.LOGIN_PATH.get_url(self.school), data=data,
                                     headers=header, allow_redirects=False)

        login_state = self.__check_login_state(response.text)

        if login_state == LoginState.SUCCESS:
            self.__save_cookies(self.session)

        return login_state


    def reauth(self) -> LoginState:
        reauth_responce = self.session.get(MyPageURLs.REAUTH_TOKEN_PATH.get_url(self.school), headers=header)
        soup = BeautifulSoup(reauth_responce.text, "html.parser")
        token = soup.find(attrs={'name': '_token'}).get('value')

        posted = self.session.post(MyPageURLs.REAUTH_PATH.get_url(self.school), data={
            "url": "/result/pc/list/index", "password": self.password, "_token": token}, headers=header, allow_redirects=False)
        if "認証に失敗" in posted.text:
            print("認証に失敗しました。パスワードが正しく入力できているか確認してください。")
            return LoginState.REAUTH_FAILED

        return LoginState.SUCCESS


    def fetch_score(self) -> [SubjectScore]:
        score_res = self.session.get(MyPageURLs.SCORE_PATH.get_url(self.school), headers=header)
        if "reauth_login" in score_res.url:
            self.reauth()
            score_res = self.session.get(MyPageURLs.SCORE_PATH.get_url(self.school), headers=header)
        return self.__score_parser(score_res.text)


    def __load_cookies(self, session):
        with open(self.cookie_path, "rb") as f:
            session.cookies = pickle.load(f)

    def __save_cookies(self, session):
        with open(self.cookie_path, "wb") as f:
            pickle.dump(session.cookies, f)

    def __score_parser(self, html):
        soup = BeautifulSoup(html, "html.parser")
        subjects = [item.text for item in soup.find_all(
            attrs={'rowspan': '3'})]
        report_number = len(soup.find_all(
            attrs={'class': 'header_report_number'}))
        limit_dates = [item.text.strip() for item in soup.find_all(
            attrs={'class': 'report_limit_date'})]
        score_with_progresses = [item.text.strip() for item in soup.find_all(attrs={
            'class': 'report_progress'})]
        persents = []
        scores = []
        for index, item in enumerate(split_list(score_with_progresses, report_number)):
            if index % 2 == 0:
                persents += item
            else:
                scores += item

        # print(subjects)
        # print(report_number)
        # print(limit_dates)
        # print(score_with_progresses)

        subject_scores = []

        subject_index = -1
        for (index, (limit, score, persent)) in enumerate(zip(limit_dates, scores, persents)):
            if index % report_number == 0:
                subject_index += 1
            if limit == "-":
                continue

            subject_scores.append(
                SubjectScore(
                    subject=subjects[subject_index],
                    limit=limit,
                    percentage=int(persent.strip().strip("%")),
                    score=score
                )
            )

        for item in subject_scores:
            print(str(item))

        return subject_scores


    def __check_login_state(self, html) -> LoginState:
        if "学籍番号またはパスワードが違います" in html:
            return LoginState.WRONG_ACCOUNT
        elif "必須項目です" in html:
            return LoginState.NOT_ENTERED
        elif "パスワードのリセットを行ってください" in html:
            return LoginState.PASS_RESET
        elif "マイページを使用することはできません" in html:
            return LoginState.CANT_USE

        return LoginState.SUCCESS


    def __username2school(self, username) -> School:
        if "N" in username:
            return School.N
        elif "S" in username:
            return School.S
        else:
            return None