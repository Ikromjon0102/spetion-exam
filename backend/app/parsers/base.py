from dataclasses import dataclass, field


@dataclass
class ParsedOption:
    text: str
    is_correct: bool = False


@dataclass
class ParsedQuestion:
    prompt: str
    options: list[ParsedOption] = field(default_factory=list)
    confidence: str = "low"  # "high" | "low" — surfaced to the review UI


class BaseParser:
    def parse(self, file_bytes: bytes) -> list[ParsedQuestion]:
        raise NotImplementedError
