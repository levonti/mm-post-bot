import shlex
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedArgs:
    command: str
    positional: tuple[str, ...]
    flags: dict[str, str | bool]

    @classmethod
    def from_argv(cls, argv: list[str]) -> ParsedArgs:
        if not argv:
            return cls(command="", positional=(), flags={})

        command = argv[0].removeprefix("!")
        positional: list[str] = []
        flags: dict[str, str | bool] = {}
        idx = 1

        while idx < len(argv):
            value = argv[idx]
            if value.startswith("--") and len(value) > 2:
                flag_name = value[2:]
                next_idx = idx + 1
                if next_idx < len(argv) and not argv[next_idx].startswith("--"):
                    flags[flag_name] = argv[next_idx]
                    idx += 2
                else:
                    flags[flag_name] = True
                    idx += 1
            else:
                positional.append(value)
                idx += 1

        return cls(command=command, positional=tuple(positional), flags=flags)


def parse_command(raw_text: str) -> ParsedArgs:
    return ParsedArgs.from_argv(shlex.split(raw_text))
