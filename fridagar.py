"""
http://visindavefur.hi.is/svar.php?id=1692
"""
from datetime import date, timedelta

def get_easter(year):
    # Algorithm: http://www.smart.net/~mmontes/nature1876.html
    # Python implementation: http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return date(year, month, day)


def get_holidays(year):
    easter = get_easter(year)
    easter_offset = lambda days: easter + timedelta(days=days)

    return [
        # 1.jan
        date(year, 1, 1),
        # Skirdagur
        easter_offset(-3),
        #Fostudagurinn langi
        easter_offset(-2),
        # Paskadagur
        easter,
        # Annar i paskum
        easter_offset(+1),
        # Sumardagur fyrsti,
        date(year, 4, 19) + timedelta((7-date(year, 4, 19).weekday()+3)%7),
        # 1. mai
        date(year, 5 , 1),
        # Uppstigningardagur
        easter_offset(+39),
        # Hvitasunnudagur
        easter_offset(+49),
        # Annar i hvitasunnu
        easter_offset(+50),
        # 17. juni
        date(year, 6, 17),
        # Verslunarmannahelgi,
        date(year, 8, 1) + timedelta((7-date(year,8,1).weekday())%7),
        # Adfangadagur (eftir hadegi)
        date(year, 12, 24),
        # Joladagur
        date(year, 12, 25),
        # Annar i jolum
        date(year, 12, 26),
        # Gamlarsdagur, eftir hadegi
        date(year, 12, 31)
    ]
