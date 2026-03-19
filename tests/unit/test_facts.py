from kourai_common.facts import extract_facts, strip_facts


def test_extract_facts():
    text = 'Here is some text. <FACT category="preference" confidence="high">Player loves Python.</FACT> End.'
    facts = extract_facts(text, "techne")

    assert len(facts) == 1
    fact = facts[0]
    assert fact.category == "preference"
    assert fact.confidence == "high"
    assert fact.body == "Player loves Python."
    assert fact.source_agent == "techne"


def test_extract_multiple_facts():
    text = '<FACT confidence="low">First fact</FACT> some noise <FACT category="skill" confidence="medium">Second fact</FACT>'
    facts = extract_facts(text)

    assert len(facts) == 2
    assert facts[0].body == "First fact"
    assert facts[0].confidence == "low"

    assert facts[1].body == "Second fact"
    assert facts[1].category == "skill"
    assert facts[1].confidence == "medium"


def test_strip_facts():
    text = 'Here is some text. <FACT category="preference" confidence="high">Player loves Python.</FACT> End.'
    stripped = strip_facts(text)
    assert stripped == "Here is some text.  End."
