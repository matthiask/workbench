import sys
from collections import defaultdict

from openpyxl import load_workbook
from xlsxdocument import XLSXDocument


workbooks = [load_workbook(name) for name in sys.argv[1:]]
sheets = [wb.worksheets[0] for wb in workbooks]
users = defaultdict(
    lambda: {
        "percentage": 0,
        "gross_margin": [None for _ in sheets],
    }
)

for idx, sheet in enumerate(sheets):
    for row in list(sheet.rows)[4:]:
        users[row[0].value]["percentage"] = row[2].value
        users[row[0].value]["gross_margin"][idx] = row[3].value

xlsx = XLSXDocument()
xlsx.add_sheet("Nutzer_innen")
xlsx.table(
    ["Nutzer*in"]
    + [list(sheet.rows)[0][0].value.removeprefix("Squeeze ") for sheet in sheets]
    + ["Prozent"],
    [
        [user] + data["gross_margin"] + [data["percentage"]]
        for user, data in sorted(users.items())
    ],
)
xlsx.workbook.save("merge_squeeze.xlsx")
