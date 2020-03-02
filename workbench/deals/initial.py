from workbench.deals.models import AttributeGroup, ClosingType, Stage, ValueType


STAGES = [
    "Sammelbecken",
    "Erstkontakt",
    "Auftragsschärfung",
    "unter 80%",
    "80% später",
    "80% jetzt",
]

VALUE_TYPES = ["Beratung & Konzept", "Grafik", "Programmierung"]

SOURCES = [
    "Empfehlung",
    "Google",
    "Massenmedien",
    "FH Projekt gesehen",
    "Kaltakquise",
    "Bestehender Kunde",
    "Persönliches Netzwerk",
    "Simap",
]

SECTORS = [
    "NPO/NGO",
    "Bildung",
    "Kultur",
    "Politik",
    "Medien & Verlage",
    "Behörden & Ämter",
    "Finanzbranche",
    "Konsumgüter & Lifestyleprodukte",
    "KMU's (Ingenieurwesen, IT, Anwaltskanzlei, Buchhandlung etc.)",
    "Verbände & Gewerkschaften",
    "Wirtschaftsprüfer",
    "Versicherungen",
]

WINS = [
    "Pitch in Konkurrenz",
    "Agentur-/Offertenpräsentation in Konkurrenz",
    "Direkte Projektanfrage ohne Konkurrenz",
]
LOSS = ["Preis", "Andere Agentur (Idee)", "Vorgehen", "Sonstiges ..."]


def initial():
    for i, title in enumerate(STAGES):
        Stage.objects.create(title=title, position=10 * (i + 1))

    for i, title in enumerate(VALUE_TYPES):
        ValueType.objects.create(title=title, position=10 * (i + 1))

    group = AttributeGroup.objects.create(title="Quelle", position=10)
    for i, title in enumerate(SOURCES):
        group.attributes.create(title=title, position=10 * (i + 1))

    group = AttributeGroup.objects.create(title="Branche", position=20)
    for i, title in enumerate(SECTORS):
        group.attributes.create(title=title, position=10 * (i + 1))

    for i, title in enumerate(WINS):
        ClosingType.objects.create(
            title=title, represents_a_win=True, position=10 * (i + 1)
        )
    for i, title in enumerate(LOSS):
        ClosingType.objects.create(
            title=title, represents_a_win=False, position=10 * (i + 1 + len(WINS))
        )


initial()
