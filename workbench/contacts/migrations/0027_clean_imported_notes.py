import re

from django.db import migrations


# Lines like "(Skype,someone)" of an old import, only whole lines
SOCIAL = re.compile(
    r"^\s*\((skype|twitter|facebook|fb|xing|msn|google),.*\)\s*$", re.IGNORECASE
)
# "(Website,http://...)" and "(Websites: http://..., http://...)" anywhere;
# urlize only links bare URLs
WEBSITES = re.compile(r"\(websites?[,:]\s*([^()]+?)\s*\)", re.IGNORECASE)


def websites(match):
    return " ".join(url for url in re.split(r"[,\s]+", match[1]) if url)


def clean(notes):
    """The notes without social media lines and with bare websites, or
    ``None`` if nothing changed"""
    lines, seen, changed = [], set(), False
    for line in notes.splitlines():
        if SOCIAL.match(line):
            changed = True
            continue
        if (new := WEBSITES.sub(websites, line).strip()) == line.strip():
            lines.append(line)
            continue
        changed = True
        if new not in seen:
            seen.add(new)
            lines.append(new)
    if not changed:
        return None
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def forwards(apps, schema_editor):
    for model in ["Organization", "Person"]:
        queryset = apps.get_model("contacts", model).objects
        for pk, notes in queryset.filter(notes__contains="(").values_list(
            "pk", "notes"
        ):
            if (cleaned := clean(notes)) is not None:
                queryset.filter(pk=pk).update(notes=cleaned)


class Migration(migrations.Migration):
    dependencies = [("contacts", "0026_clean_detail_types")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
