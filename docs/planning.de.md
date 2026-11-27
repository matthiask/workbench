# Planung

Die Planung zeigt, wer in welchen Wochen woran arbeitet, neben den
Abwesenheiten und der verbleibenden Kapazität. Es geht um Stunden pro
Woche, nicht um einzelne Aufgaben. Die Planung steht zur Verfügung, wo
deine Installation sie eingeschaltet hat.

## Wo

- **Projekt**: «Planung» auf der Projektseite, mit den Meilensteinen des
  Projekts, seinen Offerten und der dafür geplanten Arbeit.
- **Person**: «Planung» auf deiner Seite (oder «geplante Arbeit» im Menü
  mit deinem Namen) zeigt deine Wochen über alle Projekte;
  «Retrospektive» zeigt die vergangenen Monate.
- **Team**- und **Kampagnen**-Seiten haben ihre eigene Planung.

## Was geplant wird

- **Geplante Arbeit**: eine Person, ein Titel, die Wochen (sie müssen
  nicht aufeinander folgen) und das **Total** der Stunden, gleichmässig
  auf die Wochen verteilt. Optional eine Offerte und ein Meilenstein.
  **Provisorische** Arbeit ist geplant, aber nicht fest, z.B. bevor eine
  Offerte akzeptiert ist.
- **Meilensteine**: ein Datum, optional der Beginn ihrer Phase und eine
  Farbe; Arbeit eines Meilensteins wird in seiner Farbe gezeichnet.
- **Kundenarbeit**: Arbeit der Kundschaft oder anderer (z.B.
  Feedbackrunden, eine Druckerei), ohne Stunden.

## Arbeit planen

- Ziehe über Wochen in der Zeile des Projekts, einer Offerte oder eines
  Meilensteins, oder klicke eine einzelne Woche an: Das Formular öffnet
  sich mit diesen Wochen.
- Ziehe einen Balken, um ihn zu verschieben, oder seine Enden, um ihn zu
  verlängern oder zu verkürzen. Das Total der Stunden bleibt gleich, die
  Stunden pro Woche ändern sich also. Änderungen werden sofort
  gespeichert.
- «Arbeit planen» im Menü einer Offerte oder Leistung auf der
  Projektseite füllt Titel, Bemerkungen und Stunden aus.
- Im Formular wählst du mehrere Wochen mit Ctrl (Cmd auf Macs).
- «Batch-Bearbeitung» im Menü des Projekts verschiebt, weist zu oder
  löscht mehrere Einträge auf einmal, oder macht sie fest. Über Projekte
  hinweg, z.B. um die künftige Arbeit von jemandem zu übergeben, der
  geht, mit `wb planning work batch`.

Workbench warnt, wenn Arbeit nach ihrem Meilenstein geplant ist.
Geschlossene Projekte erhalten keine neue geplante Arbeit. Beim
Schliessen eines Projekts, Ablehnen einer Offerte oder Verlieren eines
Geschäfts fragt Workbench, ob die geplante Arbeit nach der laufenden
Woche gelöscht werden soll; vergangene Arbeit bleibt. Meilensteine
nach der laufenden Woche werden mitgelöscht, wenn ihnen keine geplante
Arbeit und keine Kundenarbeit mehr bleibt. Ein gewonnenes
Geschäft ändert die Planung nicht: Mache provisorische Arbeit selbst
fest.

## Kapazität

Die verbleibende Kapazität pro Woche sind deine Arbeitstage mal deine
«Planungsstunden pro Tag» (in deinen Einstellungen) und dein Pensum,
minus Feiertage, Abwesenheiten und **alle** deine geplante Arbeit, auch
die provisorische. Negative Kapazität erscheint orange: Jemand ist
überbucht. Die Startseite führt provisorische Arbeit der nächsten Wochen
auf, damit sie entschieden wird.

## Eine Planung importieren

«Planung importieren» im Menü des Projekts erstellt einen Prompt für ein
KI-Werkzeug mit dem Projekt, seinen Offerten, den Personen (mit
Kurznamen) und ihren Abwesenheiten (ohne Gründe). Der Prompt enthält die
Beschreibung und die Kundschaft des Projekts; füge ihn nur in Werkzeuge
ein, mit denen du das teilen darfst. Füge die Antwort wieder ein:
«Prüfen» zeigt Fehler, Warnungen und eine Vorschau, «Importieren»
übernimmt sie.

## Mails

Am Montag erhalten Beteiligte eine Mail mit den Änderungen der letzten
Woche an geplanter Arbeit und Meilensteinen ihrer Projekte und mit den
Abwesenheiten von Personen in ihren Projekten. Niemand erhält eine Mail,
die nur eigene Änderungen aufführt. Ein Projekt kann diese Mails für
alle abschalten.
