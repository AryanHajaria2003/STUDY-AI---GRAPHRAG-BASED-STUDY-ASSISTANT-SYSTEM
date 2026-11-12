
import re


UNIT_PATTERN = re.compile(
    r"^\s*UNIT\s+([IVXLCDM]+|\d+)\s*:?\s*(.*?)\s*$",
    re.IGNORECASE
)

PAPER_PATTERN = re.compile(
    r"^\s*Paper\s*:\s*(.+?)\s*$",
    re.IGNORECASE
)

CODE_PATTERN = re.compile(
    r"^\s*Code\s*:\s*(\S+)",
    re.IGNORECASE
)

STOP_PATTERN = re.compile(
    r"^(text books?|reference books?|suggested readings|field work|"
    r"note\s*:|course outcomes|instructions to paper setters|"
    r"maximum marks|nues paper)\b",
    re.IGNORECASE
)

NOISE_PATTERN = re.compile(
    r"^(ability to|students will|course will|overall|this paper|"
    r"filled on a scale|po\d+|co\s*\d+|guru gobind|"
    r"mca\(se\)|applicable from|syllabus of)\b",
    re.IGNORECASE
)


def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip(" :-,.;\t")


def valid_topic(topic):
    topic = clean(topic)

    if not 3 <= len(topic) <= 90:
        return False

    if len(topic.split()) > 12:
        return False

    if NOISE_PATTERN.search(topic) or STOP_PATTERN.match(topic):
        return False

    if re.fullmatch(r"[\d\s()./-]+", topic):
        return False

    return True


def extract_topics(line):
    line = clean(line)

    if not line or STOP_PATTERN.match(line):
        return []

    line = re.sub(
        r"\(\s*\d+\s*hours?\s*\)",
        "",
        line,
        flags=re.IGNORECASE
    )

    topics = []

    if ":" in line:
        heading, description = line.split(":", 1)

        if valid_topic(heading):
            topics.append(clean(heading))

        line = description

    else:
        match = re.match(r"^(.{3,70}?)\s+-\s+(.+)$", line)

        if match:
            heading = clean(match.group(1))

            if valid_topic(heading):
                topics.append(heading)

            line = match.group(2)

    for part in re.split(r"[,;]", line):
        part = clean(part)

        if valid_topic(part):
            topics.append(part)

    return list(dict.fromkeys(topics))


def extract_entities(pages):
    entities = {}

    current_subject = None
    current_unit = None

    def add_entity(
        entity_type, name, page,
        subject=None, unit=None,
        code=None, title=None, source_line=None
    ):
        name = clean(name)

        key = (
            entity_type,
            (subject or "").casefold(),
            (unit or "").casefold(),
            name.casefold()
        )

        if key not in entities:
            entities[key] = {
                "type": entity_type,
                "name": name,
                "page_numbers": set(),
                "subject": subject,
                "unit": unit,
                "source_lines": []
            }

        entity = entities[key]
        entity["page_numbers"].add(page)

        if code:
            entity["code"] = code

        if title:
            entity["title"] = title

        if source_line and source_line not in entity["source_lines"]:
            entity["source_lines"].append(source_line)

    for page_data in pages:
        page_number = int(page_data["page_number"])

        for raw_line in page_data["text"].splitlines():
            line = clean(raw_line)

            if not line:
                continue

            paper_match = PAPER_PATTERN.match(line)

            if paper_match:
                current_subject = clean(paper_match.group(1))
                current_unit = None

                add_entity(
                    "Subject",
                    current_subject,
                    page_number,
                    source_line=line
                )
                continue

            code_match = CODE_PATTERN.match(line)

            if code_match:
                if current_subject:
                    key = (
                        "Subject", "", "",
                        current_subject.casefold()
                    )

                    if key in entities:
                        entities[key]["code"] = code_match.group(1)

                continue

            if not current_subject:
                continue

            unit_match = UNIT_PATTERN.match(line)

            if unit_match:
                unit_number = unit_match.group(1).upper()
                current_unit = f"Unit {unit_number}"

                unit_title = clean(unit_match.group(2))

                add_entity(
                    "Unit",
                    current_unit,
                    page_number,
                    subject=current_subject,
                    title=unit_title or None,
                    source_line=line
                )

                if valid_topic(unit_title):
                    add_entity(
                        "Topic",
                        unit_title,
                        page_number,
                        subject=current_subject,
                        unit=current_unit,
                        source_line=line
                    )

                continue

            if STOP_PATTERN.match(line):
                current_unit = None
                continue

            if not current_unit:
                continue

            for topic in extract_topics(line):
                add_entity(
                    "Topic",
                    topic,
                    page_number,
                    subject=current_subject,
                    unit=current_unit,
                    source_line=line
                )

    return [
        {
            **entity,
            "page_numbers": sorted(entity["page_numbers"])
        }
        for entity in entities.values()
    ]


if __name__ == "__main__":
    from document_processing import process_pdf

    document = process_pdf("data3/mca(syllabus).pdf")
    entities = extract_entities(document["pages"])

    print("Total entities:", len(entities))

    for entity in entities:
        print(entity)
