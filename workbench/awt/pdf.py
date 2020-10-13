import datetime as dt
import io
import zipfile

from django.http import HttpResponse
from django.utils.formats import date_format
from django.utils.text import slugify
from django.utils.translation import gettext as _

from workbench.tools.formats import days, hours, local_date_format
from workbench.tools.pdf import PDFDocument, mm
from workbench.tools.xlsx import WorkbenchXLSXDocument


def annual_working_time_pdf(statistics):
    if len(statistics["statistics"]) == 1:
        response = HttpResponse(
            user_stats_pdf(statistics["statistics"][0]), content_type="application/pdf"
        )
        response["Content-Disposition"] = 'attachment; filename="awt.pdf"'
        return response

    with io.BytesIO() as buf:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for data in statistics["statistics"]:
                zf.writestr(
                    "%s-%s.pdf"
                    % (
                        slugify(data["user"].get_full_name()),
                        data["months"]["year"].year,
                    ),
                    user_stats_pdf(data),
                )
            xlsx = WorkbenchXLSXDocument()
            xlsx.add_sheet(_("running net work hours"))
            xlsx.table(
                [""]
                + [date_format(day, "M") for day in data["months"]["months"]]
                + [_("vacation days credit")],
                [
                    [data["user"].get_full_name()]
                    + data["running_sums"]
                    + [data["totals"]["vacation_days_credit"]]
                    for data in statistics["statistics"]
                ],
            )
            with io.BytesIO() as x:
                xlsx.workbook.save(x)
                zf.writestr("statistics.xlsx", x.getvalue())
        response = HttpResponse(buf.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="awt.zip"'
        return response


def user_stats_pdf(data):
    with io.BytesIO() as buf:
        pdf = PDFDocument(buf, font_size=7)
        pdf.init_report()

        awt_columns = [9.5 * mm for i in range(12)]
        awt_columns.append(12 * mm)
        awt_columns.insert(0, pdf.bounds.E - pdf.bounds.W - sum(awt_columns))
        awt_table_style = pdf.style.tableHead + (("TOPPADDING", (0, 1), (-1, -1), 3),)

        pdf.h1(data["user"])
        pdf.spacer(1 * mm)
        pdf.p(_("annual working time"))
        pdf.spacer(3 * mm)

        table = []
        table.append(
            [data["months"]["year"]]
            + [date_format(day, "M") for day in data["months"]["months"]]
            + [_("Total")]
        )

        table.append(
            [_("target days for full time employment")]
            + data["months"]["target_days"]
            + [data["totals"]["target_days"]]
        )
        table.append(
            [_("pensum")]
            + ["%.0f%%" % p for p in data["months"]["percentage"]]
            + ["%.0f%%" % data["totals"]["percentage"]]
        )
        table.append(
            [_("vacation days available")]
            + [days(value) for value in data["months"]["available_vacation_days"]]
            + [days(data["totals"]["available_vacation_days"])]
        )
        table.append(
            [
                "%s (%s)"
                % (
                    _("target time"),
                    data["months"]["year"].pretty_working_time_per_day,
                )
            ]
            + [hours(value) for value in data["months"]["target"]]
            + [hours(data["totals"]["target"])]
        )
        table.append(
            [_("vacation days taken")]
            + [
                days(value) if value else ""
                for value in data["months"]["absence_vacation"]
            ]
            + [days(data["totals"]["absence_vacation"])]
        )
        table.append(
            [_("sickness days")]
            + [
                days(value) if value else ""
                for value in data["months"]["absence_sickness"]
            ]
            + [days(data["totals"]["absence_sickness"])]
        )
        if data["totals"]["absence_paid"]:
            table.append(
                [_("Paid leave")]
                + [
                    days(value) if value else ""
                    for value in data["months"]["absence_paid"]
                ]
                + [days(data["totals"]["absence_paid"])]
            )
        if data["totals"]["absence_correction"]:
            table.append(
                [_("Working time correction")]
                + [
                    days(value) if value else ""
                    for value in data["months"]["absence_correction"]
                ]
                + [days(data["totals"]["absence_correction"])]
            )
        if data["totals"]["vacation_days_correction"]:
            table.append(
                [_("vacation days correction")]
                + [
                    days(value) if value else ""
                    for value in data["months"]["vacation_days_correction"]
                ]
                + [days(data["totals"]["vacation_days_correction"])]
            )
        table.append(
            [_("countable absence hours")]
            + [hours(value) if value else "" for value in data["absences_time"]]
            + [hours(data["totals"]["absences_time"])]
        )
        table.append(
            [_("logged hours")]
            + [hours(value) if value else "" for value in data["months"]["hours"]]
            + [hours(data["totals"]["hours"])]
        )
        table.append(
            [_("working time")]
            + [hours(value) if value else "" for value in data["working_time"]]
            + [hours(data["totals"]["working_time"])]
        )
        table.append(
            [_("net work hours per month")]
            + [hours(value) for value in data["monthly_sums"]]
            + [""]
        )

        pdf.table(table, awt_columns, awt_table_style)
        pdf.spacer(1 * mm)

        table = []
        table.append(
            [_("running net work hours")]
            + [hours(value) for value in data["running_sums"]]
            + [hours(data["totals"]["running_sum"])]
        )

        if data["totals"]["vacation_days_credit"]:
            table.append(
                [_("vacation days credit")]
                + [""] * 12
                + [days(data["totals"]["vacation_days_credit"])]
            )

        table.append([_("balance")] + [""] * 12 + [hours(data["totals"]["balance"])])

        pdf.table(
            table,
            awt_columns,
            awt_table_style + (("FONT", (0, 0), (-1, 0), "Rep", pdf.style.fontSize),),
        )
        pdf.spacer()

        table = []
        for employment in data["employments"]:
            table.append(
                [
                    employment,
                    employment.percentage,
                    "%.0f" % employment.vacation_weeks,
                    employment.notes,
                ]
            )

        if table:
            pdf.table(
                [[_("employment"), _("percentage"), _("vacation weeks"), _("notes")]]
                + table,
                pdf.table_columns((35 * mm, 15 * mm, 20 * mm, None)),
                awt_table_style + (("ALIGN", (0, 0), (-1, -1), "LEFT"),),
            )
            pdf.spacer()

        for key, reason in [
            ("absence_vacation", _("vacation days")),
            ("absence_sickness", _("sickness days")),
            ("absence_paid", _("Paid leave")),
            ("absence_correction", _("Working time correction")),
        ]:
            table = [
                [absence.pretty_period, days(absence.days), absence.description]
                for absence in data["absences"][key]
            ]
            if table:
                pdf.table(
                    [[reason, "", ""]] + table,
                    pdf.table_columns((35 * mm, 15 * mm, None)),
                    awt_table_style + (("ALIGN", (0, 0), (-1, -1), "LEFT"),),
                )
                pdf.spacer()

        pdf.p(_("Generated on %(day)s") % {"day": local_date_format(dt.date.today())})

        pdf.generate()
        return buf.getvalue()
