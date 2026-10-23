"""A small, static PowerShell lexer and remote-download pipeline heuristic."""

from dataclasses import dataclass
import re

from sentinel.core.command_guard import CommandFinding, CommandSyntaxError


@dataclass(frozen=True)
class _Token:
    value: str
    kind: str


_REMOTE = re.compile(r"https?://[^/\s?#]+(?:[/?#][^\s]*)?", re.IGNORECASE)
_DOWNLOADERS = {"invoke-webrequest", "invoke-restmethod", "iwr", "irm"}
_SINKS = {"invoke-expression", "iex"}
_OPERATORS = "|;\n(){}&"


def _tokens(text: str) -> list[_Token]:
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in " \t\r":
            index += 1
        elif text.startswith("`\r\n", index) or text.startswith("`\n", index):
            index += 3 if text.startswith("`\r\n", index) else 2
        elif text.startswith("<#", index):
            depth = 1
            index += 2
            while index < len(text) and depth:
                if text.startswith("<#", index):
                    depth += 1
                    index += 2
                elif text.startswith("#>", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                raise CommandSyntaxError("Comentario PowerShell sin cerrar.")
        elif char == "#":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
        elif char in ("'", '"'):
            quote = char
            index += 1
            pieces = []
            while index < len(text):
                if quote == "'" and text.startswith("''", index):
                    pieces.append("'")
                    index += 2
                elif text[index] == quote:
                    index += 1
                    break
                elif quote == '"' and text[index] == "`" and index + 1 < len(text):
                    # Retain escapes as a marker: this increment only accepts
                    # literal URLs, without evaluating string expressions.
                    pieces.append(text[index:index + 2])
                    index += 2
                else:
                    pieces.append(text[index])
                    index += 1
            else:
                raise CommandSyntaxError("Cadena PowerShell sin cerrar.")
            tokens.append(_Token("".join(pieces), "single" if quote == "'" else "double"))
        elif char in _OPERATORS:
            operator = char
            index += 1
            if char in "|&" and index < len(text) and text[index] == char:
                operator += char
                index += 1
            tokens.append(_Token(operator, "operator"))
        else:
            pieces = []
            while index < len(text) and text[index] not in " \t\r'\"" + _OPERATORS:
                if text.startswith("`\r\n", index) or text.startswith("`\n", index):
                    # Continuations are lexical joins even inside a word.
                    index += 3 if text.startswith("`\r\n", index) else 2
                elif text[index] == "`" and index + 1 < len(text):
                    # Preserve other escapes, without reinterpreting an
                    # escaped backtick as the start of a continuation.
                    pieces.append(text[index:index + 2])
                    index += 2
                else:
                    pieces.append(text[index])
                    index += 1
            tokens.append(_Token("".join(pieces), "word"))
    return tokens


def _download(stage: list[_Token]) -> bool:
    if not stage or stage[0].kind != "word" or stage[0].value.lower() not in _DOWNLOADERS:
        return False
    for token in stage[1:]:
        if token.kind == "word" and token.value.lower().split(":", 1)[0] == "-outfile":
            return False
    for token in stage[1:]:
        value = token.value
        if token.kind == "word" and value.lower().startswith("-uri:"):
            value = value[5:]
        if token.kind != "single" and ("$" in value or "`" in value):
            continue
        if _REMOTE.fullmatch(value):
            return True
    return False


def check_powershell(text: str) -> list[CommandFinding]:
    findings = []
    stage: list[_Token] = []
    source = False
    after_pipe = False
    for token in _tokens(text) + [_Token("\n", "operator")]:
        if token.kind == "operator":
            if token.value == "\n" and after_pipe:
                continue
            if source and stage and stage[0].kind == "word" and stage[0].value.lower() in _SINKS:
                findings.append(CommandFinding(
                    "CF-PS-001", "high",
                    "Una descarga remota se canaliza directamente a Invoke-Expression.",
                    "Guarda primero la descarga en un archivo sin ejecutarlo; revisa su contenido y verifica su origen e integridad antes de decidir ejecutarlo.",
                ))
            source = _download(stage) if token.value == "|" else False
            after_pipe = token.value == "|"
            stage = []
        else:
            stage.append(token)
            after_pipe = False
    return findings
