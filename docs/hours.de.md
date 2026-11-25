# Stunden erfassen

Stunden werden auf einer **Leistung** eines Projekts erfasst, am besten
gleich nach jeder erledigten Aufgabe:

- Du weisst noch, was du gemacht hast; das hilft, wenn die Arbeit später
  mit der Kundschaft besprochen wird.
- Workbench füllt die Zeit seit deinem letzten Eintrag aus, du prüfst sie
  nur noch.
- Am Ende des Tages oder der Woche gibt es nichts mehr nachzutragen.
- Pausen erfasst du nebenbei, Workbench weiss, wann sie angefangen haben.

Wenn das nicht geht (ein Anruf, jemand steht an deinem Tisch, eine
Sitzung ohne Computer), setze eine [Zeitmarke](#zeitmarken) und erfasse
die Stunden später.

## Stunden erfassen

<kbd>Ctrl-L</kbd> erfasst Stunden auf dem angezeigten Projekt, sonst
fragt Workbench zuerst nach dem Projekt (<kbd>Ctrl-Shift-L</kbd> fragt
immer). Das Formular füllt aus:

- **Stunden**: die Zeit seit deiner letzten Aktivität des Tages
  (erfasste Stunden, das Ende einer Pause, eine Zeitmarke), aufgerundet
  auf die nächste Zehntelstunde, sofern es höchstens 12 Stunden sind.
- **Leistung**: die Leistung, auf der du in diesem Projekt zuletzt
  erfasst hast.

Ein neues Projekt hat noch keine Leistungen: Fülle im selben Formular
«Neue Leistung» aus, statt eine auszuwählen. Verwende spezifische Titel
und Beschreibungen, sie landen vielleicht auf einer Offerte oder
Rechnung.

**Stunden für Verrechnung** bleiben meistens leer: Dann werden die
gearbeiteten Stunden verrechnet. Fülle sie aus, wenn eine andere Anzahl
Stunden verrechnet werden soll als gearbeitet wurde; sie haben beim
Erstellen von Rechnungen Vorrang, die gearbeiteten Stunden zählen
weiterhin für alles rund um die Zeit (Arbeitszeit, Planung, Budgets in
Stunden).

Stunden werden in der laufenden Woche erfasst (ab Montag, nicht vor
dem 1. Januar); mehr als einen Tag im Voraus fragt Workbench nach, ob das
stimmt, mehr als eine Woche geht nicht. Auf geschlossenen Projekten kann
noch 14 Tage lang erfasst werden.

Das Formular warnt vor Einträgen, die falsch aussehen: ein Duplikat
deines vorherigen Eintrags, ein kürzlich geschlossenes Projekt, ein schon
verrechneter Eintrag, Stunden für Verrechnung tiefer oder viel höher als
die gearbeiteten Stunden und, wo eingeschaltet, spätes Erfassen und zu
wenig Pausen. Prüfe den Eintrag und wähle «Warnungen ignorieren», wenn er
stimmt.

Auf der [Kommandozeile](cli.de.md) erfassen `wb hours create` und
`wb costs create` Stunden und Kosten mit denselben Prüfungen; Warnungen
halten mit ihrem Code an, `--ignore-warning CODE` akzeptiert sie.

## Zeitmarken

Eine Zeitmarke hält fest, wann du eine Aufgabe beendet oder begonnen
hast, mit Notizen und optional dem Projekt. Später machst du daraus auf
der [Zeitmarken-Seite](#die-zeitmarken-seite) erfasste Stunden oder
Pausen.

- **Stop** beendet eine Aufgabe: Die Notizen beschreiben die Arbeit, die
  du gerade abgeschlossen hast.
- **Start** beginnt eine Aufgabe: Die Notizen beschreiben, was du
  anfängst. Verwende es am Morgen und nach Pausen, damit die erste
  Aufgabe des Tages oder nach der Pause ihren Anfang hat. Ein Start mit
  einem darauf folgenden Stop ist eine Aufgabe, ihre Notizen werden
  zusammengefügt.
- **Notizen** werden zur Beschreibung der erfassten Stunden.
- **Projekt**: die ID eines Projekts oder Wörter aus seinem Titel oder
  der Kundschaft, wie bei der Projektsuche. Ein eindeutiger Treffer unter
  deinen gepinnten Projekten gewinnt, sonst muss der Treffer unter allen
  offenen Projekten eindeutig sein. Projekt und Leistung werden dann beim
  Erfassen der Stunden ausgefüllt.
- **Zeit**: eine Uhrzeit von heute, falls du den Knopf nicht im richtigen
  Moment gedrückt hast.

Der **Controller**, ein kleines Fenster für Zeitmarken, öffnet sich mit
«Controller» auf der Zeitmarken-Seite. Er funktioniert ohne Anmeldung,
du kannst ihn also auf den Home-Bildschirm deines Telefons legen und
Zeitmarken auch fern vom Computer setzen. Sein Link enthält deinen
persönlichen Schlüssel: Gib ihn nicht weiter.

Auf der Kommandozeile machen `wb timestamps start` und `wb timestamps
stop` dasselbe (`wb timestamps --help`).

## Die Zeitmarken-Seite

<kbd>Ctrl-T</kbd> (oder «Zeitmarken» auf der Startseite) zeigt deinen Tag
in Abschnitten: jeder mit seinen Zeiten, seiner Dauer, dem Projekt und den
Notizen. Erfasste Stunden und Pausen gehören dazu, auch die ohne
Zeitmarke erfassten.

- **+ Stunden** öffnet das Logbuch-Formular mit Tag, Dauer, Notizen und
  Projekt des Abschnitts.
- **+ Pause** erfasst den Abschnitt als Pause mit seinem Anfang und Ende.
- **Aufteilen** teilt einen Abschnitt in mehrere Teile (in Zehntelstunden),
  z.B. wenn du ohne Zeitmarke dazwischen an mehreren Projekten gearbeitet
  hast. Erfasse jeden Teil einzeln.
- Das Kreuz löscht eine Zeitmarke, die du nicht brauchst.
- Lücken von mehr als zwei Minuten zwischen Abschnitten erscheinen als
  «&lt;entdeckt&gt;» und lassen sich wie die anderen erfassen.
- Erfasste Abschnitte verlinken ihren Eintrag.

An einem anderen Tag für diesen Tag erfasste Stunden stehen am Ende, ohne
Zeiten. Mit den Pfeilen siehst du frühere Tage. Workbench erinnert dich,
wenn viele Zeitmarken der laufenden Woche noch nicht erfasst sind.

## Pausen

<kbd>Ctrl-B</kbd> (oder der Plus-Knopf unten links) erfasst eine Pause:
Sie beginnt bei deiner letzten Aktivität des Tages und endet jetzt, passe
beides bei Bedarf an. <kbd>Ctrl-Shift-B</kbd> zeigt deine Pausen. Wo
eingeschaltet, warnt Workbench, wenn du mehr als 5,5, 7 oder 9 Stunden am
Tag mit weniger als 15, 30 oder 60 Minuten Pause gearbeitet hast.

## Kosten erfassen

<kbd>Ctrl-K</kbd> (oder der Plus-Knopf) erfasst Kosten auf einer Leistung
eines Projekts, wie Stunden: Spesen, Lizenzen, ein Druckauftrag. Interne
Kosten gehören auf ein internes Projekt.

- **Fremdkosten**: was an andere bezahlt wurde, inklusive MwSt.
- **Kosten**: was der Kundschaft verrechnet wird. «100%» und «115%»
  übernehmen die Fremdkosten, letzteres mit einem Zuschlag. Workbench
  warnt, wenn die Fremdkosten höher sind als die Kosten.
- **Mit eigenem Geld bezahlt** (wo Spesenabrechnungen eingeschaltet
  sind) markiert Spesen, die zurückerstattet werden; sie brauchen
  Fremdkosten. Spesen in einer anderen Währung behalten ihre
  Originalwährung und ihren Originalbetrag.
- «Zahlungen» → «Spesenabrechnungen» fasst deine noch nicht
  zurückerstatteten Spesen zu einer Abrechnung zusammen. Eine
  abgeschlossene Abrechnung bleibt abgeschlossen.

**Warum inklusive MwSt?** Fremdkosten sind das Total auf der Quittung,
inklusive MwSt, denn das wurde bezahlt (und wird bei Spesen
zurückerstattet). Die Kosten sind wie alles auf einer Rechnung ein
Betrag ohne MwSt: Die Rechnung schlägt die MwSt darauf. Doppelt bezahlt
wird die MwSt trotzdem nicht: Die Firma zieht die MwSt der Quittung als
Vorsteuer ab, die Kundschaft bezahlt die MwSt einmal, auf der Rechnung.
Z.B. eine Quittung über 108.10 inklusive 8,1% MwSt: Fremdkosten 108.10,
Kosten 108.10 («100%»), die Rechnung schlägt 8.76 MwSt darauf.

Verrechnete Kosten behalten ihre Beträge.

## Der Timer

Der Timer (im Menü mit deinem Namen) gibt es noch, empfohlen sind aber
Zeitmarken.

Seine Aktivitäten bleiben, wo du sie hinschiebst. Auf einem kleineren
Bildschirm scrollt die Seite, und die Knöpfe − und + unter «+ Pause»
machen die Aktivitäten in diesem Browser kleiner oder grösser.

Um mehrere Aktivitäten auf einmal zu verschieben, ziehst du auf einer
leeren Stelle ein Rechteck über sie (oder klickst mit gedrückter
Umschalttaste auf ihre Titel) und ziehst dann eine davon. Ein Klick auf
eine leere Stelle oder Escape hebt die Auswahl auf.

«Anordnen» legt die ausgewählten Aktivitäten (oder alle) in Reihen aus,
die ins Fenster passen. «Rückgängig» stellt die vorherigen Positionen
wieder her, bis eine der Aktivitäten verschoben wird.
