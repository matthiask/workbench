#!/usr/bin/env python3

import datetime


# ----------------------------------------------------------------------------#
# Autor: Stephan John                                                         #
# Version: 1.0                                                                #
# Datum: 02.04.2010                                                           #
# http://www.it-john.de/weblog/2010/apr/01/berechnung-von-feiertagen/         #
# ----------------------------------------------------------------------------#


class EasterDay:
    """
    Berechnung des Ostersonntages nach der Formel von Heiner Lichtenberg für
    den gregorianischen Kalender. Diese Formel stellt eine Erweiterung der
    Gaußschen Osterformel dar
    Infos unter http://de.wikipedia.org/wiki/Gaußsche_Osterformel
    """

    def __init__(self, year):
        self.year = year

    def get_k(self):
        """
        Säkularzahl:
        K(X) = X div 100
        """

        k = self.year // 100
        return k

    def get_m(self):
        """
        säkulare Mondschaltung:
        M(K) = 15 + (3K + 3) div 4 − (8K + 13) div 25
        """

        k = self.get_k()
        m = 15 + (3 * k + 3) // 4 - (8 * k + 13) // 25
        return m

    def get_s(self):
        """
        säkulare Sonnenschaltung:
        S(K) = 2 − (3K + 3) div 4
        """

        k = self.get_k()
        s = 2 - (3 * k + 3) // 4
        return s

    def get_a(self):
        """
        Mondparameter:
        A(X) = X mod 19
        """

        a = self.year % 19
        return a

    def get_d(self):
        """
        Keim für den ersten Vollmond im Frühling:
        D(A,M) = (19A + M) mod 30
        """

        a = self.get_a()
        m = self.get_m()
        d = (19 * a + m) % 30
        return d

    def get_r(self):
        """
        kalendarische Korrekturgröße:
        R(D,A) = D div 29 + (D div 28 − D div 29) (A div 11)
        """

        a = self.get_a()
        d = self.get_d()
        r = d // 29 + (d // 28 - d // 29) * (a // 11)
        return r

    def get_og(self):
        """
        Ostergrenze:
        OG(D,R) = 21 + D − R
        """

        d = self.get_d()
        r = self.get_r()
        og = 21 + d - r
        return og

    def get_sz(self):
        """
        erster Sonntag im März:
        SZ(X,S) = 7 − (X + X div 4 + S) mod 7
        """

        s = self.get_s()
        sz = 7 - (self.year + self.year // 4 + s) % 7
        return sz

    def get_oe(self):
        """
        Entfernung des Ostersonntags von der Ostergrenze
        (Osterentfernung in Tagen):
        OE(OG,SZ) = 7 − (OG − SZ) mod 7
        """

        og = self.get_og()
        sz = self.get_sz()
        oe = 7 - (og - sz) % 7
        return oe

    def get_os(self):
        """
        das Datum des Ostersonntags als Märzdatum
        (32. März = 1. April usw.):
        OS = OG + OE
        """

        og = self.get_og()
        oe = self.get_oe()
        os = og + oe
        return os

    def get_date(self):
        """
        Ausgabe des Ostersonntags als datetime-Objekt
        """

        os = self.get_os()
        if os > 31:
            month = 4
            day = os - 31
        else:
            month = 3
            day = os
        easter_day = datetime.date(self.year, month, day)
        return easter_day


def get_public_holidays(year):
    easter = EasterDay(year).get_date()

    return {
        datetime.date(year, 1, 1): "Neujahr",
        datetime.date(year, 1, 2): "Berchtoldstag",
        easter - datetime.timedelta(days=2): "Karfreitag",
        easter: "Ostersonntag",
        easter + datetime.timedelta(days=1): "Ostermontag",
        datetime.date(year, 5, 1): "Tag der Arbeit",
        easter + datetime.timedelta(days=39): "Auffahrt",
        easter + datetime.timedelta(days=49): "Pfingstsonntag",
        easter + datetime.timedelta(days=50): "Pfingstmontag",
        datetime.date(year, 8, 1): "Nationalfeiertag",
        datetime.date(year, 12, 25): "Weihnachtstag",
        datetime.date(year, 12, 26): "Stephanstag",
    }


if __name__ == "__main__":
    year = datetime.date.today().year
    for i in range(year, year + 3):
        days = get_public_holidays(i)
        print(
            "\n".join(
                "%s: %s" % (day.strftime("%d.%m.%Y"), name)
                for day, name in sorted(days.items())
            )
        )
        print()
