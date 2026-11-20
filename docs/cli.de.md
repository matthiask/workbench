# Kommandozeile und API-Tokens

`wb` ist das Kommandozeilen-Werkzeug von Workbench: Es sucht, zeigt und
ändert Projekte, Offerten, Rechnungen, Geschäfte, Kontakte, erfasste
Stunden und Kosten, Abwesenheiten und die Planung und gibt die Berichte aus. Assistenten wie
Claude Code verwenden es ebenfalls.

## Installieren

«API-Tokens» im Menü mit deinem Namen zeigt die Befehle für dein
Workbench:

```
uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"
wb login https://workbench.example.com/ --read
```

`wb login` öffnet den Browser, wo du `wb` auf diesem Computer
autorisierst. Wähle `--read` (nur lesen) oder `--write` (lesen und
schreiben); Lesen genügt für Werkzeuge und Assistenten, die nur Fragen
beantworten. Fahre im Browser nur fort, wenn du `wb` gerade selbst
gestartet hast. `wb me` zeigt, als wer du angemeldet bist.

Wenn Workbench ein neueres `wb` braucht, sagt es das und gibt den Befehl
zum Aktualisieren aus (`uv tool upgrade --python … workbench-cli`).

`wb skills install` installiert die Skills für Claude Code, die mit `wb`
kommen (Offerten schreiben, Stunden erfassen, Kontakte erfassen, Planung,
Controlling und mehr). Führe es nach Aktualisierungen mit neuen Skills
erneut aus.

## wb verwenden

Befehle folgen `wb <Nomen> <Verb>`, z.B. `wb projects search`,
`wb offers show 1234`, `wb deals update`. `wb --help` und
`wb <Nomen> --help` zeigen alles. Die meisten Befehle akzeptieren
`--json`, Änderungen `--dry-run`.

Änderungen werden geprüft wie in der Weboberfläche. Wo die Weboberfläche
eine Warnung zeigt, hält `wb` an und gibt den Code der Warnung aus;
`--ignore-warning CODE` akzeptiert sie, nachdem du sie geprüft hast.

`wb hours create SERVICE STUNDEN BESCHREIBUNG` und `wb costs create`
[erfassen Stunden und Kosten](hours.de.md) mit den Prüfungen und
Warnungen des Logbuch-Formulars, `update` und `delete` ändern und
entfernen sie wie in der Weboberfläche. `wb services search --project ID`
findet die Leistung. `wb timestamps start` und `wb timestamps stop`
setzen [Zeitmarken](hours.de.md#zeitmarken).

## API-Tokens

`wb login` erstellt sein Token selbst. Auf Computern ohne Browser
erstellst du ein Token auf der Seite «API-Tokens» und verwendest
`wb login URL --token`.

- Ein Token handelt in deinem Namen, mit deinem Zugriff: nur lesen oder
  lesen und schreiben. Der Verlauf zeigt Änderungen damit unter deinem
  Namen, markiert mit «API»; das Audit-Log der Administration zeigt auch
  das Token.
- Es wird nur einmal angezeigt, kopiere es sofort.
- Es läuft 30 Tage nach der letzten Verwendung ab; jede Verwendung
  verlängert es.
- Das Papierkorb-Symbol widerruft es sofort, ebenso `wb tokens delete ID`
  (`wb tokens` listet deine Tokens auf). `wb logout` widerruft das Token,
  das `wb` auf diesem Computer verwendet. Tokens von Personen, die
  gegangen sind, funktionieren nicht mehr.
