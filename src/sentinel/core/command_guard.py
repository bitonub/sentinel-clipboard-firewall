"""Heuristic Bash inspection. Input is tokenized as data, never executed."""

from dataclasses import dataclass
import re
import shlex


@dataclass(frozen=True)
class CommandFinding:
    rule_id: str
    severity: str
    explanation: str
    suggestion: str


class CommandSyntaxError(ValueError):
    """The heuristic tokenizer could not read the input."""


_OPERATORS = "|;&()\n"
_REMOTE = re.compile(r"(?:https?|ftps?|sftp)://", re.IGNORECASE)


def _words(stage: list[str]) -> list[str]:
    # Each token is decoded independently, retaining the distinction between
    # quoted punctuation (data) and unquoted pipeline operators.
    return [word for token in stage for word in shlex.split(token)]


def _download(stage: list[str]) -> bool:
    words = _words(stage)
    if not words or words[0].rsplit("/", 1)[-1] not in ("curl", "wget"):
        return False
    command = words[0].rsplit("/", 1)[-1]
    short, long = ("o", "--output") if command == "curl" else ("O", "--output-document")
    output = None
    remote = False
    index = 1
    while index < len(words):
        word = words[index]
        target = None
        if word == long:
            target = ""
        elif word.startswith(long + "="):
            output = word[len(long) + 1:]
        elif word.startswith("-") and not word.startswith("--") and short in word[1:]:
            # Includes attached short arguments and wget's common -qO- form.
            target = word[word.index(short, 1) + 1:]
        else:
            remote = remote or bool(_REMOTE.match(word.removeprefix("--url=")))
        if target is not None:
            if not target:
                index += 1
                if index == len(words):
                    return False
                target = words[index]
            output = target
        index += 1
    # wget normally saves a file; '-' explicitly sends the body to stdout.
    return remote and (output == "-" or (command == "curl" and output is None))


def _shell(stage: list[str]) -> bool:
    words = _words(stage)
    if not words or words[0].rsplit("/", 1)[-1] not in ("bash", "sh"):
        return False
    stdin = False
    index = 1
    while index < len(words):
        word = words[index]
        if word in ("--", "-"):
            index += 1
            break
        if word in ("--rcfile", "--init-file"):
            index += 2
            continue
        if word.startswith("--"):
            if word not in ("--noprofile", "--norc", "--posix", "--restricted", "--verbose", "--login"):
                return False
        elif word.startswith(("-", "+")):
            flags = word[1:]
            if "c" in flags:
                return False
            if "s" in flags:
                stdin = word.startswith("-")
            if flags.endswith(("o", "O")):
                index += 1  # Option name, e.g. bash -o pipefail.
        else:
            break
        index += 1
    return stdin or index >= len(words)


def _without_comments(text: str) -> str:
    """Remove Bash comments before shlex sees quotes inside them."""
    pieces = []
    quote = None
    word_start = True
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and quote != "'" and index + 1 < len(text):
            following = text[index + 1]
            if following != "\n":
                pieces.append(text[index:index + 2])
                word_start = False
            index += 2
            continue
        if quote:
            pieces.append(char)
            if char == quote:
                quote = None
        elif char == "#" and word_start:
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        else:
            pieces.append(char)
            if char in ("'", '"'):
                quote = char
                word_start = False
            else:
                word_start = char in " \t\r\n|;&()<>"
        index += 1
    return "".join(pieces)


def check_command(text: str) -> list[CommandFinding]:
    lexer = shlex.shlex(_without_comments(text), posix=False, punctuation_chars=_OPERATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    findings = []
    stage: list[str] = []
    source = False
    after_pipe = False
    try:
        tokens = []
        for token in lexer:
            if all(char in _OPERATORS for char in token):
                tokens.extend(re.findall(r"\|\||&&|\|&|[|;&()\n]", token))
            else:
                tokens.append(token)
        for token in tokens + ["\n"]:
            if token == "\n" and after_pipe:
                continue
            if token in ("|", "|&", "||", "&&", ";", "&", "(", ")", "\n"):
                if source and _shell(stage):
                    findings.append(CommandFinding(
                        "CF-BASH-001", "high",
                        "Una descarga remota se entrega directamente por pipe a un intérprete Bash o sh.",
                        "Descarga primero a un archivo sin ejecutarlo; revisa su contenido y verifica su origen e integridad antes de decidir ejecutarlo.",
                    ))
                source = _download(stage) if token in ("|", "|&") else False
                after_pipe = token in ("|", "|&")
                stage = []
            else:
                stage.append(token)
                after_pipe = False
    except ValueError:
        raise CommandSyntaxError("No se pudo analizar la sintaxis del comando.") from None
    return findings
