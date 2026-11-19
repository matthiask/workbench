# Rechnungen

| Typ | |
| --- | --- |
| Fixbetrag | Ein Betrag, mit Titel und Beschreibung. Der einfachste Typ, wenn die Rechnung die Leistungen nicht aufführen muss. |
| Anzahlung | Ein Betrag auf einem Projekt, der von späteren Rechnungen abgezogen wird. |
| Leistungen | Leistungen des Projekts, gemäss Offerte oder gemäss Logbuch. |
| Gutschrift | Ein Betrag zugunsten der Kundschaft, als positive Zahl eingegeben. |

## Eine Rechnung erstellen

Auf dem Projekt führt «Neu» die Typen unter «Rechnung» auf; «Rechnung
erstellen» im Menü einer Offerte erstellt eine Leistungsrechnung für
diese Offerte. Workbench warnt, wenn das Projekt
schon eine Rechnung in Vorbereitung hat und wenn Fixbetrags- und
Leistungsrechnungen gemischt werden, was dieselbe Arbeit doppelt
verrechnen könnte.

«Das ist die Schlussrechnung, schliesse das Projekt» schliesst das
Projekt beim Speichern.

Die Kundschaft ist immer eine Organisation. Für eine Privatperson
erstellst du eine Organisation und setzt «ist Privatperson»: Ihr Name
fällt dann in Adressen weg. Rechnungen ohne Projekt (z.B. für den
Verkauf alter Geräte) erstellst du bei einer Person oder Organisation mit
«Neu» → «Rechnung»; sie können nur Fixbeträge sein.

## Leistungsrechnungen

Wähle oben die Offerte, die du verrechnest, oder «Keine Offerte,
Leistungen selbst auswählen». Mit einer Offerte übernimmt die Rechnung
ihren Titel, ihre Beschreibung, ihre Leistungen und ihren Rabatt. Pro
Leistung wählt **Verrechnung** die Quelle:

- **gemäss Offerte**: die offerierten Stunden und Kosten. Vorgabe, wenn
  etwas offeriert wurde, die Offerte nicht abgelehnt ist und die Leistung
  noch nicht verrechnet wurde. Verknüpft auch die bisher erfassten
  Einträge.
- **gemäss Logbuch**: die erfassten und noch nicht verrechneten Stunden
  und Kosten. Nachdem die Offerte verrechnet wurde, ist das der
  **Mehraufwand**: die danach erfasste Arbeit.

Die Positionen lassen sich anpassen (Stunden, Ansatz, Kosten, Titel,
Beschreibung). Hinweise zeigen erfasste Stunden und Kosten, die gemäss
Offerte nicht verrechnet werden. Der **Logbuch-Abgrenzungstermin** lässt
spätere Einträge für die nächste Rechnung übrig, und «Erfassung sperren»
schliesst eine Leistung für die Erfassung. Nur Leistungen mit etwas zu
verrechnen werden aufgeführt, «Alle Leistungen des Projekts anzeigen»
zeigt den Rest. Eine mit 0 verrechnete Leistung verknüpft trotzdem ihre
offenen Einträge und schreibt sie so ab.

## Fixbeträge und Anzahlungen

Die Hilfe zum Betrag zeigt das Total exkl. MwSt der akzeptierten
Offerten (nach ihren Rabatten) und was bisher verrechnet wurde. «Bisher
verrechnet» ist die verrechnete Arbeit (Zwischentotal minus Rabatt der
Fixbetrags- und Leistungsrechnungen), Anzahlungen stehen separat, mit dem
Teil, der noch nicht angewendet wurde. Eine Fixbetragsrechnung kann den
Rest einsetzen: Die Anzahlungen, die sie anwendet, werden davon
abgezogen, nicht doppelt gezählt.

Ein Prozentsatz setzt diesen Anteil der akzeptierten Offerten ein oder,
wenn ihre Leistungen Fremdkosten haben, der akzeptierten Offerten ohne
Fremdkosten, auf 5 Rappen gerundet. Anzahlungen und Fixbeträge zeigen
keinen Rabatt: Ihre Basis ist schon nach den Rabatten der Offerten.

## Anzahlungen

Fixbetrags- und Leistungsrechnungen auf einem Projekt mit Anzahlungen
bieten «Anzahlungen anwenden» an: Die versandten oder bezahlten und noch
nicht angewendeten Anzahlungen werden abgezogen. Eine auf eine versandte
Rechnung angewendete Anzahlung lässt sich nicht mehr ändern; storniere
zuerst jene Rechnung.

## Versenden, Zahlungen und Stornieren

| Status | |
| --- | --- |
| In Vorbereitung | Wird geschrieben, lässt sich löschen. |
| Versendet | Braucht Rechnungsdatum und Fälligkeitsdatum. |
| Bezahlt | Braucht eine Zahlungsnotiz. |
| Storniert | Braucht eine Zahlungsnotiz mit dem Grund. |

- **Freigeben und versenden** schickt das PDF an die Empfänger:in,
  markiert die Rechnung als versendet und schickt der verantwortlichen
  Person eine Kopie.
- **Als bezahlt markieren** im Menü der Rechnung oder durch Zuweisen
  einer Zahlung (siehe unten).
- Rechnungen **in Vorbereitung** werden gelöscht, versandte
  **storniert** («Rechnung stornieren»). Beides gibt die erfassten
  Einträge und Anzahlungen für eine andere Rechnung frei. Eine
  stornierte Leistungsrechnung oder eine mit Anzahlungen lässt sich nicht
  wieder öffnen: Erstelle stattdessen eine neue Rechnung.

Workbench lässt dich versandte Rechnungen ändern, warnt aber. Die
Warnungen sind als Hilfe gemeint: Wenn die geänderte Rechnung von Anfang
an richtig gewesen wäre, wähle «Warnungen ignorieren». Vorsicht, wenn die
Rechnung schon bezahlt wurde oder bei der Buchhaltung angekommen ist.
Rechnungen am oder vor dem Einfrierdatum sind eingefroren:
Nur noch ihr Status und wenige Felder lassen sich ändern.

## Stapelrechnungen

«Zahlungen» → «Stapelrechnungen» erstellt periodisch (jährlich,
quartalsweise, monatlich oder wöchentlich) Fixbetragsrechnungen, einige
Tage bevor die jeweilige Periode beginnt. Neue Rechnungen werden in
Vorbereitung erstellt, als versendet markiert oder automatisch
verschickt (die Liste filtert danach); die verantwortliche Person erhält eine Mail. Mit «Projekt
erstellen?» erhält jede Rechnung ihr eigenes Wartungsprojekt und ist eine
Anzahlung darauf, die beim Verrechnen der dort erfassten Arbeit
abgezogen wird. Die Rechnungen verlinken ihre Stapelrechnung, die sie
auflistet.

## Zahlungen und Zahlungserinnerungen

Mit Zugriff auf die Buchhaltung:

- **Zahlungseingänge**: «Kontoauszug hochladen» liest den Auszug der Bank
  ein, «Zahlungseingänge zuweisen» weist jede Zahlung der versandten
  Rechnung mit demselben Total zu und markiert sie damit als bezahlt.
- **Zahlungserinnerungen** führt Rechnungen auf, die seit 15 Tagen oder
  länger fällig sind, nach Kundschaft, und erstellt oder verschickt die
  Erinnerung. «Zahlungserinnerungen aufschieben» bei einer Rechnung
  schiebt sie bis zu 60 Tage auf.

Wie Rechnungen beginnen: siehe [Offerten](offers.de.md).
