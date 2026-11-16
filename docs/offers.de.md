# Offerten

Workbench offeriert und verrechnet **Leistungen**: Arbeitspakete wie
«Kontaktformular», bepreist mit Stunden und einem Stundensatz und mit
Kosten, nicht blosse Stunden. Eine Offerte gehört zu einem Projekt und
besteht aus einigen seiner Leistungen. Offerten und Rechnungen brauchen
Zugriff aufs Controlling.

## Eine Offerte erstellen

Auf dem Projekt öffnet «Neu» → «Offerte» (oder «+ Offerte» bei «Noch
nicht offeriert») das Offertenformular. Der Titel ist zuerst derjenige
des Projekts. Unter den Angaben zur Offerte fügst du die Leistungen
hinzu:

- **Neue Leistung** fügt eine leere Zeile hinzu.
- **Bestehende Leistung** fügt eine Leistung des Projekts hinzu, die noch
  in keiner Offerte ist.
- **Zwischentitel** fügt einen Titel zwischen den Leistungen hinzu, mit
  Titel und Beschreibung und ohne Beträge.

Ziehe die Zeilen, um sie zu sortieren. Das Kreuz entfernt eine Leistung
aus der Offerte, sie kommt zurück zu «Noch nicht offeriert» und wird
nicht gelöscht.

Jede Leistung hat einen Titel, eine Beschreibung, Aufwandtyp und
Stundensatz (der Leistungstyp füllt beides aus), Stunden, Kosten und ob
sie optional ist. Fremdkosten, «Leistungserfassung erlauben» und die
externe Referenz stellst du im eigenen Formular der Leistung auf dem
Projekt ein.

## Preise

- Eine Leistung kostet ihre Stunden mal ihren Stundensatz plus ihre
  Kosten.
- Eine Leistung hat **einen** Aufwandtyp und Stundensatz, der auch für
  die darauf erfassten Stunden gilt. Offeriere Arbeit zu verschiedenen
  Ansätzen als verschiedene Leistungen.
- **Fremdkosten** sind der Teil der Kosten, der an andere bezahlt wird
  (inklusive MwSt), nicht zusätzlich.
- **Optionale** Leistungen zählen nicht zum Total; das PDF führt sie mit
  einem eigenen Total auf.
- Das Total ist die Summe der Leistungen minus Rabatt, plus MwSt,
  gerundet auf fünf Rappen.
- Auf Projekten mit Pauschalsatz erhalten neue Leistungen den
  Pauschalsatz.

## Status

| Status | |
| --- | --- |
| In Vorbereitung | Wird geschrieben, die Leistungen lassen sich ändern. |
| Leistungsgruppe | Nie versandt: gruppiert Leistungen, z.B. für die Erfassung und Budgets. Die Leistungen lassen sich ändern. |
| Offeriert | An die Kundschaft versandt; braucht «offeriert am» und «Gültig bis». |
| Akzeptiert | Die Kundschaft hat zugesagt. |
| Abgelehnt | Die Kundschaft hat abgesagt, oder eine versandte Offerte wird nicht mehr verfolgt. |
| Verworfen | Nie versandt und nicht mehr verfolgt. |

Die Leistungen offerierter, akzeptierter und abgelehnter Offerten bleiben,
wie sie versandt wurden. Um sie zu ändern, setze die Offerte zurück auf
«In Vorbereitung» und speichere, dann bearbeite die Leistungen und
setze die Offerte wieder auf ihren Status. Gib dabei das Datum, an dem
sie akzeptiert oder abgelehnt wurde, wieder bei «Geschlossen am» ein.
Das ist so vorgesehen:
Offerten sollen dem besten aktuellen Wissensstand entsprechen, z.B. wenn
eine optionale Leistung doch bestellt wird, eine Leistung wegfällt oder
sich die Stunden ändern, damit Budgets und Auswertungen stimmen.
Offerierte und akzeptierte Offerten lassen sich nicht löschen.

Beim Ablehnen oder Verwerfen einer Offerte fragt Workbench, ob ihre
geplante Arbeit nach der laufenden Woche gelöscht werden soll. Beim
Schliessen eines Projekts werden Offerten in Vorbereitung verworfen und
schon versandte abgelehnt.

**Arbeit abgeschlossen am** beendet die Erfassung auf den Leistungen der
Offerte.

## Arten von Offerten

- **Offerten** werden der Kundschaft versandt, die sie akzeptiert oder
  ablehnt. Akzeptierte Offerten sind das, was verkauft ist.
- **Leistungsgruppen** werden nie versandt. Sie gruppieren Leistungen,
  z.B. pro Jahr oder pro Meilenstein, damit sich Stunden, Budgets und
  Rechnungen pro Gruppe verfolgen lassen. Ihre Leistungen lassen sich
  weiterhin ändern, und beim Erfassen lassen sich darin neue Leistungen
  erstellen. Ihre Leistungen zählen zum Budget, aber nicht als verkauft.
  Die Offertenliste zeigt sie nur, wenn nach ihrem Status gefiltert wird.
- Offerten, die **Budget zurückbehalten** («behält Budget zurück»), sind
  akzeptierte Offerten, die nur Budget zurückbehalten. Auf ihren
  Leistungen werden keine Stunden erfasst. Die Arbeit wird auf später
  erstellten Leistungen ohne Offerte erfasst, die das zurückbehaltene
  Budget freigeben. Das Projekt zeigt das noch zurückbehaltene Budget.
  Weitere Offerten des Projekts werden zum zurückbehaltenen Budget
  dazugezählt, das Offertenformular warnt, wenn ein Projekt beides
  erhält.

## Kopien, PDFs und Geschäfte

- «Kopieren» im Menü der Offerte kopiert sie mit ihren Leistungen und
  Zwischentiteln in ein offenes Projekt, in Vorbereitung und ohne Daten.
- «PDF» zeigt die Offerte, ihr Menü lädt sie herunter, auch mit
  Unterschriftszeile. Offerten, die nicht offeriert oder akzeptiert sind,
  tragen ihren Status als Wasserzeichen. «Projektofferten» im Menü des
  Projekts fasst die Offerten des Projekts zusammen, ohne die
  abgelehnten und verworfenen.
- Offerten werden auf dem Geschäft verbunden («Offerte verbinden»). Beim
  Abschliessen des Geschäfts werden seine Offerten akzeptiert oder
  abgelehnt.

Wie aus Offerten Rechnungen werden: siehe [Rechnungen](invoices.de.md).
