#!/usr/bin/env python3
"""
Gera as imagens animadas do perfil do GitHub (pasta ``assets/``).

    python scripts/perfil.py                 # tudo (as estatísticas precisam de GITHUB_TOKEN)
    python scripts/perfil.py --exemplo       # estatísticas com dados de EXEMPLO (só para pré-visualizar)
    python scripts/perfil.py --so-estaticas  # só as imagens que não dependem de dados

Identidade visual: os tokens reais do LisFilms (``web/src/index.css``) — fundo #0b0d10, cartões
#161a20, verde #1ed760, azul LisGames #22a7ff — e a marca Lis (ponto + duas barras).

O GitHub mostra estes SVG como ``<img>``: correm animações CSS e SMIL, mas não há JavaScript nem
recursos externos. Por isso cada imagem leva a fonte Inter embutida, reduzida às letras que usa,
e os textos com posição crítica levam ``textLength`` (ficam certos mesmo com outra fonte).
Tudo respeita ``prefers-reduced-motion``: sem animação, cada imagem mostra o estado final.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import math
import os
import random
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
RECURSOS = Path(__file__).resolve().parent / "recursos"
SAIDA = RAIZ / "assets"
UTILIZADOR = os.environ.get("PERFIL_UTILIZADOR") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "thiagodanjos"

# --------------------------------------------------------------------------------------------
# Identidade (web/src/index.css do LisFilms)
# --------------------------------------------------------------------------------------------
C = {
    "bg": "#0b0d10",
    "lateral": "#08090c",
    "elevado": "#121519",
    "cartao": "#161a20",
    "cartao2": "#1d222a",
    "borda": "#252b34",
    "borda2": "#323a45",
    "texto": "#f4f6f8",
    "suave": "#9aa3ad",
    "tenue": "#7b8591",
    "verde": "#1ed760",
    "verde2": "#7cf3a8",
    "verde_suave": "#122b1b",
    "azul": "#22a7ff",
    "azul_suave": "#0c2334",
    "discord": "#5865f2",
    "discord2": "#9aa2ff",
    "discord_suave": "#161a3a",
    "ouro": "#f5c518",
    "perigo": "#f23f42",
}
FAMILIA = "'LisInter','Inter','Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
DIAS_LONGOS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

ICONES = json.loads((RECURSOS / "icones.json").read_text(encoding="utf-8"))


def esc(s: str) -> str:
    return escape(str(s), {'"': "&quot;"})


def n(v: float) -> str:
    """Número curto para atributos (sem zeros a mais, para o SVG ficar estável e pequeno)."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


# --------------------------------------------------------------------------------------------
# Fonte: medir texto e embutir só as letras usadas
# --------------------------------------------------------------------------------------------
class Fonte:
    def __init__(self) -> None:
        self.bytes = (RECURSOS / "inter.woff2").read_bytes()
        self._inst: dict[int, tuple] = {}
        try:
            import fontTools  # noqa: F401

            self.ok = True
        except ImportError:
            self.ok = False
            print("aviso: sem fontTools — medidas aproximadas e fonte completa embutida", file=sys.stderr)

    def _metricas(self, peso: int):
        if peso not in self._inst:
            from fontTools.ttLib import TTFont
            from fontTools.varLib import instancer

            f = TTFont(io.BytesIO(self.bytes), recalcTimestamp=False)
            st = instancer.instantiateVariableFont(f, {"wght": peso})
            self._inst[peso] = (st.getBestCmap(), st["hmtx"].metrics, st["head"].unitsPerEm)
        return self._inst[peso]

    def avancos(self, texto: str, tamanho: float, peso: int = 400) -> list[float]:
        if not self.ok:
            return [tamanho * (0.32 if ch == " " else 0.58) for ch in texto]
        cmap, hmtx, upm = self._metricas(peso)
        out = []
        for ch in texto:
            g = cmap.get(ord(ch)) or cmap.get(ord("?"))
            out.append(hmtx[g][0] * tamanho / upm)
        return out

    def largura(self, texto: str, tamanho: float, peso: int = 400, espacamento: float = 0.0) -> float:
        return sum(self.avancos(texto, tamanho, peso)) + espacamento * len(texto)

    def face(self, letras: str) -> str:
        dados = self.bytes
        if self.ok:
            from fontTools import subset
            from fontTools.ttLib import TTFont

            opcoes = subset.Options()
            opcoes.flavor = "woff2"
            opcoes.layout_features = ["kern", "liga", "calt", "tnum"]
            opcoes.name_IDs = [0, 1, 2]
            opcoes.notdef_outline = True
            f = TTFont(io.BytesIO(self.bytes), recalcTimestamp=False)
            sub = subset.Subsetter(opcoes)
            sub.populate(text="".join(sorted(set(letras + " ?"))))
            sub.subset(f)
            buf = io.BytesIO()
            f.flavor = "woff2"
            f.save(buf)
            dados = buf.getvalue()
        b64 = base64.b64encode(dados).decode()
        return (
            "@font-face{font-family:'LisInter';font-style:normal;font-weight:100 900;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )


FONTE = Fonte()

BASE_CSS = (
    f"text{{font-family:{FAMILIA};font-kerning:normal;}}"
    ".fb{transform-box:fill-box;transform-origin:center;}"
    ".fe{transform-box:fill-box;transform-origin:left center;}"
    ".fbase{transform-box:fill-box;transform-origin:center bottom;}"
    "@keyframes surgir{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}"
    "@keyframes aparecer{from{opacity:0;}to{opacity:1;}}"
    "@keyframes crescer{from{opacity:0;transform:scale(.85);}to{opacity:1;transform:none;}}"
    "@keyframes pulso{0%,100%{opacity:1;}50%{opacity:.35;}}"
    "@keyframes respirar{0%,100%{opacity:.55;transform:scale(1);}50%{opacity:1;transform:scale(1.08);}}"
    "@keyframes flutuar{0%,100%{transform:translateY(0);}50%{transform:translateY(-4px);}}"
    "@keyframes deriva1{0%,100%{transform:translate(0,0);}50%{transform:translate(38px,-16px);}}"
    "@keyframes deriva2{0%,100%{transform:translate(0,0);}50%{transform:translate(-34px,18px);}}"
    "@keyframes deriva3{0%,100%{transform:translate(0,0);}50%{transform:translate(22px,20px);}}"
    "@keyframes piscar{0%,49%{opacity:1;}50%,100%{opacity:0;}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important;}}"
)


def documento(largura: int, altura: int, titulo: str, descricao: str, css: str, corpo: str) -> str:
    letras = "".join(unescape(t) for t in re.findall(r">([^<>]+)<", corpo)) + titulo + descricao
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="titulo descricao">\n'
        f'<title id="titulo">{esc(titulo)}</title>\n<desc id="descricao">{esc(descricao)}</desc>\n'
        f"<style>{FONTE.face(letras)}{BASE_CSS}{css}</style>\n{corpo}\n</svg>\n"
    )


# --------------------------------------------------------------------------------------------
# Peças comuns
# --------------------------------------------------------------------------------------------
def texto(
    x: float,
    y: float,
    conteudo: str,
    tamanho: float,
    peso: int = 400,
    cor: str = C["texto"],
    ancora: str = "start",
    espacamento: float | None = None,
    ajustar: bool = False,
    extra: str = "",
) -> str:
    """``conteudo`` já em XML (pode ter <tspan>); ``ajustar`` fixa a largura medida."""
    attrs = [f'x="{n(x)}"', f'y="{n(y)}"', f'font-size="{n(tamanho)}"', f'font-weight="{peso}"', f'fill="{cor}"']
    if ancora != "start":
        attrs.append(f'text-anchor="{ancora}"')
    if espacamento is not None:
        attrs.append(f'letter-spacing="{n(espacamento)}"')
    if ajustar:
        simples = unescape(re.sub(r"<[^>]+>", "", conteudo))
        attrs.append(f'textLength="{n(FONTE.largura(simples, tamanho, peso))}" lengthAdjust="spacingAndGlyphs"')
    return f'<text {" ".join(attrs)}{extra}>{conteudo}</text>'


def icone(nome: str, x: float, y: float, tamanho: float = 18, cor: str = C["verde"], traco: float = 2, extra: str = "") -> str:
    return (
        f'<g transform="translate({n(x)} {n(y)}) scale({tamanho / 24:.4f})" fill="none" stroke="{cor}" '
        f'stroke-width="{n(traco)}" stroke-linecap="round" stroke-linejoin="round"{extra}>{ICONES["linhas"][nome]}</g>'
    )


def luminancia(hexa: str) -> float:
    r, g, b = (int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def logo_marca(slug: str, x: float, y: float, tamanho: float = 16) -> str:
    m = ICONES["marcas"][slug]
    cor = m["cor"] if luminancia(m["cor"]) > 0.1 else C["texto"]
    return f'<path transform="translate({n(x)} {n(y)}) scale({tamanho / 24:.4f})" fill="{cor}" d="{m["d"]}"/>'


def marca_lis(x: float, y: float, escala: float = 1.0, cor: str = C["verde"], brilho: bool = True, classe_barras: str = "") -> str:
    """A marca Lis: ponto (cor da secção) + barra branca + barra da cor. 26×20 na escala 1."""
    s = escala
    partes = []
    if brilho:
        partes.append(f'<circle cx="{n(x + 5 * s)}" cy="{n(y + 10 * s)}" r="{n(9 * s)}" fill="{cor}" opacity=".35" filter="url(#desfoque)"/>')
    partes.append(f'<circle cx="{n(x + 5 * s)}" cy="{n(y + 10 * s)}" r="{n(5 * s)}" fill="{cor}"/>')
    b1 = f' class="{classe_barras} b1"' if classe_barras else ""
    b2 = f' class="{classe_barras} b2"' if classe_barras else ""
    partes.append(f'<rect{b1} x="{n(x + 14 * s)}" y="{n(y)}" width="{n(4 * s)}" height="{n(20 * s)}" rx="{n(2 * s)}" fill="{C["texto"]}"/>')
    partes.append(f'<rect{b2} x="{n(x + 22 * s)}" y="{n(y)}" width="{n(4 * s)}" height="{n(20 * s)}" rx="{n(2 * s)}" fill="{cor}"/>')
    return "".join(partes)


DEFS_COMUNS = (
    '<filter id="desfoque" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="6"/></filter>'
    '<filter id="halo" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="14"/></filter>'
    '<pattern id="pontos" width="22" height="22" patternUnits="userSpaceOnUse">'
    '<circle cx="1" cy="1" r=".9" fill="#ffffff" fill-opacity=".05"/></pattern>'
)


def radial(id_: str, cor: str, opacidade: float) -> str:
    return (
        f'<radialGradient id="{id_}"><stop offset="0" stop-color="{cor}" stop-opacity="{opacidade}"/>'
        f'<stop offset="1" stop-color="{cor}" stop-opacity="0"/></radialGradient>'
    )


def pilula(x: float, y: float, rotulo: str, cor: str, fundo: str, tamanho: float = 9.5, centro: bool = False) -> tuple[str, float]:
    """Etiqueta com ponto a pulsar. Devolve (svg, largura)."""
    esp = 1.8
    w = FONTE.largura(rotulo, tamanho, 800, esp) + 34
    if centro:
        x -= w / 2
    h = 24
    svg = (
        f'<g><rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{h}" rx="{h / 2}" fill="{fundo}" '
        f'stroke="{cor}" stroke-opacity=".35"/>'
        f'<circle cx="{n(x + 14)}" cy="{n(y + h / 2)}" r="3.2" fill="{cor}" style="animation:pulso 1.8s ease-in-out infinite"/>'
        + texto(x + 24, y + h / 2 + tamanho * 0.36, esc(rotulo), tamanho, 800, cor, espacamento=esp)
        + "</g>"
    )
    return svg, w


# --------------------------------------------------------------------------------------------
# 1. Abertura (hero)
# --------------------------------------------------------------------------------------------
FRASES = [
    "Estudante de Desenvolvimento Web e Multimédia",
    "Criador do LisFilms, do LisSecurity e do LisDiscord",
    "Aplicações completas, do backend à interface",
    "De Mogi das Cruzes, Brasil, para Leiria, Portugal",
]

FOTOGRAMAS = [
    ("clapperboard", "Filmes", "reviews e notas"),
    ("tv", "Séries", "temporadas"),
    ("sparkles", "Animes", "episódios"),
    ("gamepad-2", "Jogos", "LisGames"),
    ("bookmark", "Watchlist", "e coleções"),
    ("popcorn", "Maratonas", "em grupo"),
    ("message-circle", "Mensagens", "e grupos"),
    ("trophy", "Prémios", "da comunidade"),
    ("lock", "LisSecurity", "cofre offline"),
    ("bot", "LisDiscord", "bot e backups"),
]


def abertura() -> str:
    W, H, TB = 860, 420, 44
    cx = W / 2
    r = random.Random(7)
    css = []
    defs = [DEFS_COMUNS]
    corpo = []

    defs.append(f'<clipPath id="quadro"><rect width="{W}" height="{H}" rx="22"/></clipPath>')
    defs.append(radial("aurora1", C["verde"], 0.30) + radial("aurora2", C["azul"], 0.16) + radial("aurora3", C["verde2"], 0.14))
    defs.append(
        '<linearGradient id="feixe" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#ffffff" stop-opacity=".16"/><stop offset=".55" stop-color="#ffffff" stop-opacity=".04"/>'
        '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
    )
    defs.append(
        '<radialGradient id="vinheta" cx="50%" cy="55%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".6"/></radialGradient>'
    )
    defs.append(
        f'<linearGradient id="marcaVerde" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["verde"]}"/>'
        f'<stop offset=".55" stop-color="{C["verde2"]}"/><stop offset="1" stop-color="{C["verde"]}"/></linearGradient>'
    )
    defs.append(
        '<linearGradient id="brilhoNome" gradientUnits="userSpaceOnUse" x1="0" y1="190" x2="150" y2="120">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".75"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        '<animateTransform attributeName="gradientTransform" type="translate" values="-260 0;1000 0;1000 0" '
        'keyTimes="0;.32;1" dur="7s" begin="2.6s" repeatCount="indefinite"/></linearGradient>'
    )
    dobras = "".join(
        f'<stop offset="{i / 14:.4f}" stop-color="{"#11151a" if i % 2 else "#06070a"}"/>' for i in range(15)
    )
    defs.append(f'<linearGradient id="dobras" x1="0" y1="0" x2="1" y2="0">{dobras}</linearGradient>')
    defs.append(
        f'<radialGradient id="sombraEmblema"><stop offset=".35" stop-color="{C["lateral"]}" stop-opacity=".96"/>'
        f'<stop offset="1" stop-color="{C["lateral"]}" stop-opacity="0"/></radialGradient>'
    )
    defs.append(
        '<linearGradient id="bordaE" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0b0d10"/>'
        '<stop offset="1" stop-color="#0b0d10" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="bordaD" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#0b0d10"/>'
        '<stop offset="1" stop-color="#0b0d10" stop-opacity="0"/></linearGradient>'
    )

    palco = []
    palco.append(f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>')
    palco.append(f'<rect y="{TB}" width="{W}" height="{H - TB}" fill="url(#pontos)"/>')
    palco.append(f'<ellipse cx="190" cy="170" rx="300" ry="170" fill="url(#aurora1)" style="animation:deriva1 11s ease-in-out infinite"/>')
    palco.append(f'<ellipse cx="700" cy="330" rx="260" ry="150" fill="url(#aurora2)" style="animation:deriva2 13s ease-in-out infinite"/>')
    palco.append(f'<ellipse cx="560" cy="120" rx="220" ry="120" fill="url(#aurora3)" style="animation:deriva3 9s ease-in-out infinite"/>')

    # feixe do projetor e poeira
    css.append(
        "@keyframes tremer{0%,100%{opacity:.9;}8%{opacity:.62;}12%{opacity:.95;}37%{opacity:.75;}41%{opacity:1;}"
        "66%{opacity:.7;}70%{opacity:.92;}}"
    )
    palco.append(
        f'<g style="animation:tremer 5s steps(1) infinite"><polygon points="{cx - 26},{TB} {cx + 26},{TB} {W - 120},{H} 120,{H}" fill="url(#feixe)"/>'
        f'<ellipse cx="{cx}" cy="{TB + 1}" rx="70" ry="5" fill="#ffffff" opacity=".22" filter="url(#desfoque)"/></g>'
    )
    for i in range(3):
        dx = (-18, 12, 26)[i]
        css.append(
            f"@keyframes poeira{i}{{0%{{opacity:0;transform:translate(0,0);}}25%{{opacity:.55;}}75%{{opacity:.45;}}"
            f"100%{{opacity:0;transform:translate({dx}px,-46px);}}}}"
        )
    for _ in range(34):
        y = r.uniform(TB + 30, H - 20)
        meia = 26 + (y - TB) / (H - TB) * (cx - 146)
        x = r.uniform(cx - meia, cx + meia)
        dur = r.uniform(6, 13)
        palco.append(
            f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r.uniform(0.6, 1.6))}" fill="#ffffff" opacity=".2" '
            f'style="animation:poeira{r.randrange(3)} {dur:.1f}s linear infinite -{r.uniform(0, dur):.1f}s"/>'
        )

    # cantos de visor + REC
    for (x0, y0, sx, sy) in ((22, TB + 18, 1, 1), (W - 22, TB + 18, -1, 1), (22, H - 96, 1, -1), (W - 22, H - 96, -1, -1)):
        palco.append(
            f'<path d="M{x0} {y0 + 14 * sy}V{y0}H{x0 + 14 * sx}" fill="none" stroke="#ffffff" stroke-opacity=".28" '
            'stroke-width="1.6" stroke-linecap="round"/>'
        )
    palco.append(f'<circle cx="46" cy="{TB + 29}" r="3.4" fill="{C["perigo"]}" style="animation:piscar 1.6s infinite"/>')
    palco.append(texto(55, TB + 32.5, "REC", 9, 800, C["suave"], espacamento=2))
    palco.append(texto(W - 44, TB + 32.5, "24 FPS · LEIRIA", 9, 800, C["tenue"], "end", espacamento=2))

    # etiqueta
    etiq, _ = pilula(cx, 92, "EM EXIBIÇÃO · LEIRIA, PORTUGAL", C["verde"], C["verde_suave"], 9.5, centro=True)
    palco.append(f'<g style="animation:surgir .8s cubic-bezier(.22,1,.36,1) 1.5s both">{etiq}</g>')

    # nome com halo e brilho a passar
    # as duas palavras posicionadas à mão (larguras medidas na fonte + textLength): o espaço entre
    # elas não depende de cada visualizador tratar bem os espaços dentro de <tspan>
    tam_n, peso_n, trk, yn = 64, 900, -1.6, 180
    w1 = FONTE.largura("Thiago", tam_n, peso_n) + trk * 5
    w_esp = FONTE.largura(" ", tam_n, peso_n)
    w2 = FONTE.largura("Anjos", tam_n, peso_n) + trk * 4
    xa = cx - (w1 + w_esp + w2) / 2
    xb = xa + w1 + w_esp

    def palavras(cor1: str, cor2: str, extra: str = "") -> str:
        return (
            f'<text x="{n(xa)}" y="{yn}" font-size="{tam_n}" font-weight="{peso_n}" fill="{cor1}" textLength="{n(w1)}" '
            f'lengthAdjust="spacingAndGlyphs"{extra}>Thiago</text>'
            f'<text x="{n(xb)}" y="{yn}" font-size="{tam_n}" font-weight="{peso_n}" fill="{cor2}" textLength="{n(w2)}" '
            f'lengthAdjust="spacingAndGlyphs"{extra}>Anjos</text>'
        )

    css.append("@keyframes haloPulso{0%,100%{opacity:.28;}50%{opacity:.5;}}")
    palco.append(
        '<g style="animation:surgir 1s cubic-bezier(.22,1,.36,1) 1.6s both">'
        f'<g filter="url(#halo)" opacity=".35" style="animation:haloPulso 4s ease-in-out infinite">{palavras("#ffffff", C["verde"])}</g>'
        + palavras(C["texto"], "url(#marcaVerde)")
        + palavras("url(#brilhoNome)", "url(#brilhoNome)")
        + "</g>"
    )

    # máquina de escrever (SMIL: funciona dentro de <img> em todos os navegadores)
    tam, peso, ybase = 17, 500, 224
    janela, escrever, apagar, segurar = 5.0, 1.6, 0.45, 3.9
    total = janela * len(FRASES)
    eventos_cursor: list[tuple[float, float]] = []
    for i, frase in enumerate(FRASES):
        av = FONTE.avancos(frase, tam, peso)
        larg = sum(av)
        x0 = cx - larg / 2
        pref = [0.0]
        for a in av:
            pref.append(pref[-1] + a)
        ini = i * janela
        ev: list[tuple[float, float]] = [(ini, 0.0)]
        nch = len(frase)
        for k in range(1, nch + 1):
            ev.append((ini + 0.05 + k * escrever / nch, pref[k]))
        for k in range(1, nch + 1):
            ev.append((ini + segurar + k * apagar / nch, pref[nch - k]))
        tempos = ([0.0] if ini > 0 else []) + [t for t, _ in ev]
        valores = ([0.0] if ini > 0 else []) + [v for _, v in ev]
        kt = ";".join(f"{t / total:.5f}" for t in tempos)
        vs = ";".join(n(v) for v in valores)
        # sem SMIL (visualizadores estáticos) fica a primeira frase inteira; com SMIL começa vazia
        base = n(larg + 2) if i == 0 else "0"
        defs.append(
            f'<clipPath id="escrita{i}"><rect x="{n(x0 - 1)}" y="{ybase - 19}" width="{base}" height="26">'
            '<set attributeName="width" to="0" begin="0s" dur="2.2s"/>'
            f'<animate attributeName="width" values="{vs}" keyTimes="{kt}" dur="{total}s" begin="2.2s" '
            f'calcMode="discrete" repeatCount="indefinite"/></rect></clipPath>'
        )
        if i == 0:
            x_fim0 = x0 + larg + 2
        palco.append(
            f'<g clip-path="url(#escrita{i})">'
            + texto(x0, ybase, esc(frase), tam, peso, "#d2d9e0", ajustar=True)
            + "</g>"
        )
        eventos_cursor += [(t, x0 + v + 2) for t, v in ev]
    eventos_cursor.sort()
    kt = ";".join(f"{t / total:.5f}" for t, _ in eventos_cursor)
    vs = ";".join(n(v) for _, v in eventos_cursor)
    x_ini = eventos_cursor[0][1]
    palco.append(
        f'<rect x="{n(x_fim0)}" y="{ybase - 16}" width="2.2" height="21" rx="1.1" fill="{C["verde"]}" '
        'style="animation:aparecer .3s 2.1s both">'
        f'<set attributeName="x" to="{n(x_ini)}" begin="0s" dur="2.2s"/>'
        f'<animate attributeName="x" values="{vs}" keyTimes="{kt}" dur="{total}s" begin="2.2s" calcMode="discrete" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></rect>'
    )

    # família Lis
    familia = [("Films", C["verde"]), ("Games", C["azul"]), ("Security", C["verde"]), ("Discord", C["discord2"])]
    tam_f, h_f = 12, 28
    largs = [FONTE.largura("Lis" + suf, tam_f, 700) + 36 for suf, _ in familia]
    total_f = sum(largs) + 10 * (len(familia) - 1)
    x = cx - total_f / 2
    css.append("@keyframes ondaChip{0%,100%{opacity:0;}6%{opacity:.9;}18%{opacity:0;}}")
    for i, ((suf, cor), w) in enumerate(zip(familia, largs)):
        y = 256
        palco.append(
            f'<g style="animation:surgir .7s cubic-bezier(.22,1,.36,1) {2.0 + i * 0.12:.2f}s both">'
            f'<rect x="{n(x)}" y="{y}" width="{n(w)}" height="{h_f}" rx="{h_f / 2}" fill="{C["cartao"]}" stroke="{C["borda2"]}"/>'
            f'<rect x="{n(x)}" y="{y}" width="{n(w)}" height="{h_f}" rx="{h_f / 2}" fill="none" stroke="{cor}" stroke-width="1.4" '
            f'opacity="0" style="animation:ondaChip 6s ease-in-out {3 + i * 0.5:.1f}s infinite"/>'
            f'<circle cx="{n(x + 15)}" cy="{y + h_f / 2}" r="3.6" fill="{cor}"/>'
            + texto(x + 25, y + 18.2, f'Lis<tspan fill="{cor}">{suf}</tspan>', tam_f, 700, C["texto"])
            + "</g>"
        )
        x += w + 10

    # película a correr
    y0, hp, passo = H - 76, 76, 144
    fita = []
    for k in range(2):
        for i, (ic, rot, sub) in enumerate(FOTOGRAMAS):
            fx = (k * len(FOTOGRAMAS) + i) * passo + 8
            fita.append(
                f'<rect x="{fx}" y="{y0 + 14}" width="{passo - 12}" height="48" rx="8" fill="{C["cartao"]}" stroke="{C["borda"]}"/>'
                f'<rect x="{fx + 10}" y="{y0 + 24}" width="28" height="28" rx="8" fill="{C["verde_suave"]}"/>'
                + icone(ic, fx + 15, y0 + 29, 18, C["verde"])
                + texto(fx + 46, y0 + 35, esc(rot), 12, 700, C["texto"])
                + texto(fx + 46, y0 + 50, esc(sub), 9.5, 500, C["tenue"])
            )
    furos = "".join(
        f'<rect x="{x}" y="{y0 + 4}" width="9" height="5" rx="1.5" fill="{C["cartao2"]}"/>'
        f'<rect x="{x}" y="{y0 + hp - 9}" width="9" height="5" rx="1.5" fill="{C["cartao2"]}"/>'
        for x in range(4, passo * len(FOTOGRAMAS) * 2, 18)
    )
    deslocar = passo * len(FOTOGRAMAS)
    css.append(f"@keyframes fita{{from{{transform:translateX(0);}}to{{transform:translateX(-{deslocar}px);}}}}")
    palco.append(f'<rect y="{y0}" width="{W}" height="{hp}" fill="{C["lateral"]}"/>')
    palco.append(f'<g style="animation:fita 46s linear infinite">{furos}{"".join(fita)}</g>')
    palco.append(f'<rect y="{y0}" width="90" height="{hp}" fill="url(#bordaE)"/><rect x="{W - 90}" y="{y0}" width="90" height="{hp}" fill="url(#bordaD)"/>')
    palco.append(f'<line x1="0" y1="{y0}" x2="{W}" y2="{y0}" stroke="{C["borda"]}"/>')

    palco.append(f'<rect y="{TB}" width="{W}" height="{H - TB}" fill="url(#vinheta)"/>')

    # cortinas de abertura (estado final = abertas; sem animação ficam abertas)
    css.append(
        "@keyframes abrirE{from{transform:translateX(0);}to{transform:translateX(-450px);}}"
        "@keyframes abrirD{from{transform:translateX(0);}to{transform:translateX(450px);}}"
        ".cortE{transform:translateX(-450px);animation:abrirE 1.35s cubic-bezier(.75,0,.2,1) .75s both;}"
        ".cortD{transform:translateX(450px);animation:abrirD 1.35s cubic-bezier(.75,0,.2,1) .75s both;}"
        "@keyframes sumir{0%{opacity:1;transform:none;}100%{opacity:0;transform:scale(.92);}}"
        ".emblema{opacity:0;animation:sumir .5s ease-in .5s both;}"
    )
    meio = W / 2
    palco.append(
        f'<g class="cortE"><rect y="{TB}" width="{meio}" height="{H - TB}" fill="url(#dobras)"/>'
        f'<rect x="{meio - 2}" y="{TB}" width="2" height="{H - TB}" fill="{C["verde"]}" opacity=".7"/></g>'
        f'<g class="cortD"><rect x="{meio}" y="{TB}" width="{meio}" height="{H - TB}" fill="url(#dobras)"/>'
        f'<rect x="{meio}" y="{TB}" width="2" height="{H - TB}" fill="{C["verde"]}" opacity=".7"/></g>'
    )
    palco.append(
        f'<g class="emblema fb"><ellipse cx="{meio}" cy="236" rx="170" ry="90" fill="url(#sombraEmblema)"/>'
        f'{marca_lis(meio - 34, 196, 2.6)}'
        + texto(meio, 278, "LISFILMS APRESENTA", 10.5, 800, C["suave"], "middle", 4)
        + "</g>"
    )

    # barra de título (como a do LisSecurity)
    barra = [f'<rect width="{W}" height="{TB}" fill="{C["lateral"]}"/>', f'<line x1="0" y1="{TB}" x2="{W}" y2="{TB}" stroke="{C["borda"]}"/>']
    barra.append(marca_lis(18, 15, 0.7, brilho=False))
    barra.append(texto(43, 27, f'Lis<tspan fill="{C["verde"]}">Films</tspan>', 14, 800, C["texto"], espacamento=-0.3))
    barra.append(texto(111, 27, "/ thiagodanjos", 11.5, 500, C["tenue"]))
    bx, bw = cx - 160, 320
    barra.append(f'<rect x="{bx}" y="10" width="{bw}" height="24" rx="12" fill="{C["elevado"]}" stroke="{C["borda"]}"/>')
    barra.append(icone("search", bx + 12, 16, 12, C["tenue"], 2.4))
    barra.append(texto(bx + 32, 26, "Pesquisar páginas e ações…", 11, 500, C["tenue"]))
    barra.append(f'<rect x="{bx + bw - 50}" y="14" width="40" height="16" rx="4" fill="{C["cartao"]}" stroke="{C["borda2"]}"/>')
    barra.append(texto(bx + bw - 30, 25.5, "Ctrl K", 9, 700, C["suave"], "middle"))
    px = W - 240
    barra.append(f'<rect x="{px}" y="11" width="116" height="22" rx="11" fill="{C["verde_suave"]}" stroke="{C["verde"]}" stroke-opacity=".3"/>')
    barra.append(icone("lock", px + 10, 16, 12, C["verde"], 2.4))
    barra.append(texto(px + 28, 25.5, "Cofre trancado", 10.5, 700, C["verde"]))
    for i, ic in enumerate(("minus", "square", "x")):
        barra.append(icone(ic, W - 102 + i * 32, 16, 12 if ic != "square" else 11, C["suave"], 2))

    corpo.append(f"<defs>{''.join(defs)}</defs>")
    corpo.append(f'<g clip-path="url(#quadro)">{"".join(palco)}{"".join(barra)}</g>')
    corpo.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{C["borda"]}"/>')
    return documento(
        W,
        H,
        "Thiago Anjos — LisFilms",
        "Abertura animada: as cortinas abrem-se e aparece o nome Thiago Anjos, com frases escritas à máquina "
        "e uma película com as secções do LisFilms.",
        "".join(css),
        "\n".join(corpo),
    )


# --------------------------------------------------------------------------------------------
# 2. Cartazes dos projetos
# --------------------------------------------------------------------------------------------
def arte_lisfilms(cor: str, css: list[str]) -> str:
    cx, cy = 135, 140
    a = []
    css.append(
        "@keyframes onda{0%{opacity:.5;transform:scale(.55);}100%{opacity:0;transform:scale(1.25);}}"
        "@keyframes eq1{0%,100%{transform:scaleY(1);}50%{transform:scaleY(.72);}}"
        "@keyframes eq2{0%,100%{transform:scaleY(.8);}50%{transform:scaleY(1);}}"
        ".b1{animation:eq1 2.2s ease-in-out infinite;}.b2{animation:eq2 2.2s ease-in-out infinite;}"
    )
    for i in range(3):
        a.append(
            f'<circle class="fb" cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{cor}" stroke-width="1.4" opacity="0" '
            f'style="animation:onda 4.5s ease-out {i * 1.5}s infinite"/>'
        )
    a.append(f'<circle cx="{cx}" cy="{cy}" r="80" fill="none" stroke="#ffffff" stroke-opacity=".1" stroke-dasharray="2 7"/>')
    orbita = []
    for i, ic in enumerate(("clapperboard", "tv", "gamepad-2", "star")):
        ang = math.radians(-90 + i * 90)
        ix, iy = cx + 80 * math.cos(ang), cy + 80 * math.sin(ang)
        orbita.append(
            f'<g><animateTransform attributeName="transform" type="rotate" from="0 {n(ix)} {n(iy)}" to="-360 {n(ix)} {n(iy)}" '
            f'dur="28s" repeatCount="indefinite"/>'
            f'<circle cx="{n(ix)}" cy="{n(iy)}" r="15" fill="{C["cartao"]}" stroke="{cor}" stroke-opacity=".45"/>'
            + icone(ic, ix - 8, iy - 8, 16, cor if ic != "star" else C["ouro"])
            + "</g>"
        )
    a.append(
        f'<g><animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="28s" '
        f'repeatCount="indefinite"/>{"".join(orbita)}</g>'
    )
    a.append(f'<g class="fb" style="animation:crescer .9s cubic-bezier(.22,1,.36,1) .2s both">{marca_lis(cx - 31.2, cy - 24, 2.4, cor, classe_barras="fb")}</g>')
    return "".join(a)


def arte_lissecurity(cor: str, css: list[str], defs: list[str]) -> str:
    cx, cy = 135, 140
    r = random.Random(42)
    a = []
    defs.append(
        '<linearGradient id="desvanecer" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".25" stop-color="#fff"/><stop offset=".75" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<mask id="mascaraChuva"><rect x="20" y="44" width="230" height="196" fill="url(#desvanecer)"/></mask>'
        '<radialGradient id="fundoIcone" cx="38%" cy="46%" r="75%"><stop offset="0" stop-color="#11201a"/>'
        '<stop offset=".55" stop-color="#0c1012"/><stop offset="1" stop-color="#090b0e"/></radialGradient>'
    )
    colunas = []
    for c in range(11):
        x = 28 + c * 21.5
        dur = r.uniform(7, 13)
        chars = [r.choice("0123456789abcdef") for _ in range(14)]
        linhas = "".join(f'<tspan x="{n(x)}" dy="15">{ch}</tspan>' for ch in chars + chars)
        colunas.append(
            f'<g style="animation:chuva {dur:.1f}s linear infinite -{r.uniform(0, dur):.1f}s">'
            f'<text x="{n(x)}" y="-180" font-size="11" font-weight="600" fill="{cor}" fill-opacity="{r.uniform(.12, .28):.2f}" '
            f'text-anchor="middle">{linhas}</text></g>'
        )
    css.append("@keyframes chuva{from{transform:translateY(0);}to{transform:translateY(210px);}}")
    a.append(f'<g mask="url(#mascaraChuva)">{"".join(colunas)}</g>')
    # anel que "tranca" + marcas de mostrador
    circ = 2 * math.pi * 64
    css.append(
        f"@keyframes trancar{{0%{{stroke-dashoffset:{circ:.1f};opacity:1;}}35%{{stroke-dashoffset:0;}}82%{{opacity:1;stroke-dashoffset:0;}}"
        "100%{opacity:0;stroke-dashoffset:0;}}"
        "@keyframes marca{0%,100%{opacity:.18;}8%{opacity:1;}30%{opacity:.18;}}"
    )
    a.append(f'<circle cx="{cx}" cy="{cy}" r="64" fill="none" stroke="#ffffff" stroke-opacity=".07" stroke-width="2"/>')
    a.append(
        f'<circle cx="{cx}" cy="{cy}" r="64" fill="none" stroke="{cor}" stroke-width="2.4" stroke-linecap="round" '
        f'stroke-dasharray="{circ:.1f}" transform="rotate(-90 {cx} {cy})" style="animation:trancar 6s cubic-bezier(.65,0,.35,1) .4s infinite"/>'
    )
    for i in range(12):
        ang = math.radians(-90 + i * 30)
        a.append(
            f'<circle cx="{n(cx + 77 * math.cos(ang))}" cy="{n(cy + 77 * math.sin(ang))}" r="2.2" fill="{cor}" opacity=".18" '
            f'style="animation:marca 6s ease-in-out {0.4 + i * 0.17:.2f}s infinite"/>'
        )
    # o ícone real do LisSecurity (design/icone.svg), a 100 px
    s = 100 / 512
    a.append(
        f'<g style="animation:flutuar 4s ease-in-out infinite"><g transform="translate({cx - 50} {cy - 50}) scale({s:.5f})">'
        '<rect width="512" height="512" rx="112" fill="url(#fundoIcone)"/>'
        '<rect x="1.5" y="1.5" width="509" height="509" rx="110.5" fill="none" stroke="#ffffff" stroke-opacity=".09" stroke-width="3"/>'
        f'<g fill="{cor}" opacity=".55" filter="url(#desfoque)" transform="translate(0 0)"><circle cx="170" cy="230" r="34"/>'
        '<path d="M158 250 L149 326 Q148 336 158 336 L182 336 Q192 336 191 326 L182 250 Z"/></g>'
        f'<g fill="{cor}"><circle cx="170" cy="230" r="34"/><path d="M158 250 L149 326 Q148 336 158 336 L182 336 Q192 336 191 326 L182 250 Z"/></g>'
        f'<rect x="246" y="160" width="32" height="192" rx="16" fill="{C["texto"]}"/><rect x="310" y="160" width="32" height="192" rx="16" fill="{cor}"/>'
        "</g></g>"
    )
    return "".join(a)


def arte_lisdiscord(cor: str, css: list[str]) -> str:
    cx, cy = 135, 140
    a = []
    css.append(
        "@keyframes pestanejar{0%,90%,100%{transform:scaleY(1);}93%{transform:scaleY(.12);}96%{transform:scaleY(1);}}"
        "@keyframes bolha{0%{opacity:0;transform:translateY(6px) scale(.9);}5%{opacity:1;transform:none;}30%{opacity:1;transform:none;}"
        "36%{opacity:0;transform:translateY(-4px);}100%{opacity:0;}}"
        "@keyframes salto{0%,60%,100%{transform:translateY(0);}30%{transform:translateY(-3px);}}"
    )
    a.append(f'<circle cx="{cx}" cy="{cy}" r="86" fill="url(#brilhoArte)" style="animation:respirar 5s ease-in-out infinite" class="fb"/>')
    bot = [
        f'<ellipse cx="{cx}" cy="196" rx="44" ry="6" fill="#000" opacity=".45"/>',
        f'<line x1="{cx}" y1="112" x2="{cx}" y2="96" stroke="{cor}" stroke-width="3" stroke-linecap="round"/>',
        f'<circle cx="{cx}" cy="92" r="9" fill="{cor}" opacity=".45" filter="url(#desfoque)" style="animation:pulso 1.6s ease-in-out infinite"/>',
        f'<circle cx="{cx}" cy="92" r="5.5" fill="{cor}"/>',
        f'<rect x="86" y="131" width="8" height="22" rx="4" fill="{cor}"/><rect x="176" y="131" width="8" height="22" rx="4" fill="{cor}"/>',
        f'<rect x="93" y="110" width="84" height="66" rx="22" fill="{C["discord_suave"]}" stroke="{cor}" stroke-width="2.4"/>',
        f'<rect x="102" y="120" width="66" height="44" rx="14" fill="#0d1024"/>',
        f'<rect class="fb" x="113" y="131" width="12" height="17" rx="6" fill="#ffffff" style="animation:pestanejar 4.6s infinite"/>',
        f'<rect class="fb" x="145" y="131" width="12" height="17" rx="6" fill="#ffffff" style="animation:pestanejar 4.6s infinite"/>',
        f'<path d="M124 155 Q135 162 146 155" fill="none" stroke="{C["discord2"]}" stroke-width="2.6" stroke-linecap="round"/>',
    ]
    a.append(f'<g style="animation:flutuar 3.4s ease-in-out infinite">{"".join(bot)}</g>')
    bolhas = [
        (22, 62, "/backup", "esquerda"),
        (172, 86, "…", "direita"),
        (20, 182, "+250 moedas", "esquerda"),
        (168, 196, "/sorteio", "direita"),
    ]
    for i, (bx, by, txt, lado) in enumerate(bolhas):
        if txt == "…":
            w = 52
            conteudo = "".join(
                f'<circle cx="{bx + 15 + k * 11}" cy="{by + 13}" r="2.6" fill="{C["discord2"]}" '
                f'style="animation:salto 1s ease-in-out {k * 0.15:.2f}s infinite"/>'
                for k in range(3)
            )
        else:
            w = FONTE.largura(txt, 11, 700) + 22
            cor_txt = C["ouro"] if "moedas" in txt else C["texto"]
            conteudo = texto(bx + 11, by + 17, esc(txt), 11, 700, cor_txt)
        cauda = (
            f'<path d="M{bx + 12} {by + 25} l-2 7 l9 -7z" fill="{C["cartao2"]}"/>'
            if lado == "esquerda"
            else f'<path d="M{bx + w - 12} {by + 25} l2 7 l-9 -7z" fill="{C["cartao2"]}"/>'
        )
        a.append(
            f'<g class="fb" style="animation:bolha 9s ease-out {i * 2.25:.2f}s infinite">'
            f'<rect x="{n(bx)}" y="{by}" width="{n(w)}" height="26" rx="13" fill="{C["cartao2"]}" stroke="{cor}" stroke-opacity=".45"/>'
            f"{cauda}{conteudo}</g>"
        )
    return "".join(a)


CARTAZES = {
    "lisfilms": dict(
        cor=C["verde"],
        suave=C["verde_suave"],
        rotulo="EM EXIBIÇÃO",
        sufixo="Films",
        linhas=["A rede social de filmes, séries,", "animes e jogos. Em produção."],
        etiquetas=["React", "FastAPI", "PostgreSQL"],
        faturacao=["UM PROJETO DE THIAGO ANJOS", "PROVA DE APTIDÃO PROFISSIONAL · WEB · DESKTOP · API"],
        chamada="Visitar lisfilms.pt  →",
        descricao="Cartaz do LisFilms: a rede social de filmes, séries, animes e jogos, em produção em lisfilms.pt.",
    ),
    "lissecurity": dict(
        cor=C["verde"],
        suave=C["verde_suave"],
        rotulo="NOVA ESTREIA",
        sufixo="Security",
        linhas=["Cofre pessoal de senhas e dados", "bancários. Cifrado e sem internet."],
        etiquetas=["Rust", "Tauri", "Argon2id"],
        faturacao=["UM PROJETO DE THIAGO ANJOS", "ARGON2ID · XCHACHA20-POLY1305 · APP PARA WINDOWS"],
        chamada="Código privado · Windows",
        descricao="Cartaz do LisSecurity: cofre pessoal de senhas e dados bancários, cifrado localmente e sem internet.",
    ),
    "lisdiscord": dict(
        cor=C["discord"],
        suave=C["discord_suave"],
        rotulo="EM CARTAZ",
        sufixo="Discord",
        linhas=["Backups, moderação e 14 mini-jogos", "para servidores Discord."],
        etiquetas=["discord.js", "Backups", "Mini-jogos"],
        faturacao=["UM PROJETO DE THIAGO ANJOS", "BACKUPS · MODERAÇÃO · SORTEIOS · ECONOMIA DE MOEDAS"],
        chamada="Ver repositório  →",
        descricao="Cartaz do LisDiscord: backups, moderação e 14 mini-jogos para servidores Discord, com um bot próprio.",
    ),
}


def cartaz(chave: str, atraso: float) -> str:
    W, H = 270, 400
    d = CARTAZES[chave]
    cor = d["cor"]
    cor_titulo = C["discord2"] if chave == "lisdiscord" else cor
    css: list[str] = []
    defs = [DEFS_COMUNS]
    defs.append(f'<clipPath id="forma"><rect width="{W}" height="{H}" rx="18"/></clipPath>')
    defs.append(
        f'<linearGradient id="tinta" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{cor}" stop-opacity=".22"/>'
        f'<stop offset=".6" stop-color="{cor}" stop-opacity="0"/></linearGradient>'
    )
    defs.append(radial("brilhoArte", cor, 0.32))
    defs.append(
        '<linearGradient id="reflexo" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity=".09"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )
    p = [f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>', f'<rect width="{W}" height="{H}" fill="url(#tinta)"/>']
    p.append(f'<rect width="{W}" height="{H}" fill="url(#pontos)"/>')
    if chave != "lisdiscord":
        p.append(f'<circle class="fb" cx="135" cy="140" r="100" fill="url(#brilhoArte)" style="animation:respirar 5s ease-in-out infinite"/>')
    arte = {
        "lisfilms": lambda: arte_lisfilms(cor, css),
        "lissecurity": lambda: arte_lissecurity(cor, css, defs),
        "lisdiscord": lambda: arte_lisdiscord(cor, css),
    }[chave]()
    p.append(f'<g style="animation:aparecer .8s ease-out {atraso:.2f}s both">{arte}</g>')

    etiq, _ = pilula(16, 16, d["rotulo"], cor_titulo, d["suave"], 9)
    p.append(etiq)
    p.append(marca_lis(W - 40, 22, 0.8, cor, brilho=False))

    sobe = lambda t: f'style="animation:surgir .8s cubic-bezier(.22,1,.36,1) {atraso + t:.2f}s both"'  # noqa: E731
    p.append(
        f"<g {sobe(0.25)}>"
        + texto(W / 2, 266, f'Lis<tspan fill="{cor_titulo}">{d["sufixo"]}</tspan>', 30, 900, C["texto"], "middle", -0.6)
        + "".join(texto(W / 2, 290 + i * 16, esc(l), 11.5, 500, C["suave"], "middle") for i, l in enumerate(d["linhas"]))
        + "</g>"
    )
    largs = [FONTE.largura(e, 10, 700) + 20 for e in d["etiquetas"]]
    x = W / 2 - (sum(largs) + 6 * (len(largs) - 1)) / 2
    chips = []
    for e, w in zip(d["etiquetas"], largs):
        chips.append(
            f'<rect x="{n(x)}" y="318" width="{n(w)}" height="22" rx="11" fill="{C["cartao"]}" stroke="{C["borda2"]}"/>'
            + texto(x + w / 2, 332.6, esc(e), 10, 700, C["texto"], "middle")
        )
        x += w + 6
    p.append(f'<g {sobe(0.4)}>{"".join(chips)}</g>')
    p.append(f'<line x1="22" y1="354" x2="{W - 22}" y2="354" stroke="{C["borda"]}"/>')
    # bloco de créditos de cartaz: justificado, letras estreitas como nos cartazes de cinema
    bloco = []
    for i, linha in enumerate(d["faturacao"]):
        alvo = 226
        nat = FONTE.largura(linha, 7.2, 600)
        ajuste = "spacingAndGlyphs" if nat > alvo else "spacing"
        alvo_i = alvo if i else min(alvo, nat * 1.25)
        bloco.append(
            f'<text x="{W / 2}" y="{368 + i * 10}" font-size="7.2" font-weight="600" fill="{C["tenue"]}" text-anchor="middle" '
            f'textLength="{n(alvo_i)}" lengthAdjust="{ajuste}">{esc(linha)}</text>'
        )
    p.append("".join(bloco))
    p.append(texto(W / 2, 391, esc(d["chamada"]), 11, 800, cor_titulo, "middle"))
    # reflexo que passa
    css.append("@keyframes varrer{0%{transform:translateX(-160px);}28%,100%{transform:translateX(460px);}}")
    p.append(
        f'<g transform="rotate(18 135 200)"><rect x="-40" y="-120" width="70" height="640" fill="url(#reflexo)" '
        f'style="animation:varrer 7.5s ease-in-out {2 + atraso * 4:.1f}s infinite"/></g>'
    )
    corpo = (
        f"<defs>{''.join(defs)}</defs>"
        f'<g clip-path="url(#forma)">{"".join(p)}</g>'
        f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.25" fill="none" stroke="{cor}" stroke-opacity=".35" stroke-width="1.5"/>'
    )
    return documento(W, H, f"Lis{d['sufixo']}", d["descricao"], "".join(css), corpo)


# --------------------------------------------------------------------------------------------
# 3. Tecnologias
# --------------------------------------------------------------------------------------------
GRUPOS = [
    ("code-xml", "LINGUAGENS", [("python", "Python"), ("typescript", "TypeScript"), ("javascript", "JavaScript"), ("rust", "Rust")]),
    ("monitor", "FRONTEND", [("react", "React"), ("tailwindcss", "Tailwind CSS"), ("vite", "Vite"), ("pwa", "PWA")]),
    (
        "database",
        "BACKEND",
        [("fastapi", "FastAPI"), ("sqlalchemy", "SQLAlchemy"), ("postgresql", "PostgreSQL"), ("supabase", "Supabase"), ("firebase", "Firebase")],
    ),
    ("cpu", "DESKTOP", [("electron", "Electron"), ("tauri", "Tauri"), ("python", "Tkinter"), ("discorddotjs", "discord.js")]),
    ("server", "NUVEM E CI", [("netlify", "Netlify"), ("render", "Render"), ("githubactions", "GitHub Actions"), ("git", "Git")]),
]


def tecnologias() -> str:
    W = 860
    css = ["@keyframes realce{0%,100%{opacity:0;}5%{opacity:1;}16%{opacity:0;}}"]
    p = []
    p.append(f'<rect x="28" y="30" width="4" height="22" rx="2" fill="{C["verde"]}"/>')
    p.append(texto(42, 47, "Ferramentas com que construo", 16, 800, C["texto"]))
    p.append(texto(W - 28, 47, "no LisFilms, no LisSecurity e no LisDiscord", 10.5, 500, C["tenue"], "end"))
    y = 76
    i_chip = 0
    total_chips = sum(len(g[2]) for g in GRUPOS)
    ciclo = 7.0
    for gi, (ic, rotulo, itens) in enumerate(GRUPOS):
        p.append(f'<line x1="28" y1="{y - 7}" x2="{W - 28}" y2="{y - 7}" stroke="{C["borda"]}" stroke-dasharray="2 5"/>')
        p.append(f'<rect x="28" y="{y + 1}" width="30" height="30" rx="9" fill="{C["verde_suave"]}"/>')
        p.append(icone(ic, 35, y + 8, 16, C["verde"]))
        p.append(texto(68, y + 20, rotulo, 9.5, 800, C["suave"], espacamento=1.6))
        x = 178
        for slug, titulo in itens:
            w = 36 + FONTE.largura(titulo, 12.5, 600) + 14
            atraso = 0.15 + i_chip * 0.05
            onda = i_chip * ciclo / total_chips
            p.append(
                f'<g style="animation:surgir .6s cubic-bezier(.22,1,.36,1) {atraso:.2f}s both">'
                f'<rect x="{n(x)}" y="{y}" width="{n(w)}" height="32" rx="10" fill="{C["cartao"]}" stroke="{C["borda"]}"/>'
                f'<rect x="{n(x)}" y="{y}" width="{n(w)}" height="32" rx="10" fill="{C["verde"]}" fill-opacity=".06" stroke="{C["verde"]}" '
                f'stroke-opacity=".8" opacity="0" style="animation:realce {ciclo}s ease-in-out {1.5 + onda:.2f}s infinite"/>'
                + logo_marca(slug, x + 11, y + 8, 16)
                + texto(x + 36, y + 20.5, esc(titulo), 12.5, 600, C["texto"], ajustar=True)
                + "</g>"
            )
            x += w + 10
            i_chip += 1
        y += 48
    H = y + 14
    corpo = (
        f"<defs>{DEFS_COMUNS}</defs>"
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="{C["bg"]}" stroke="{C["borda"]}"/>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="url(#pontos)"/>' + "".join(p)
    )
    return documento(
        W,
        H,
        "Tecnologias",
        "Python, TypeScript, JavaScript, Rust, React, Tailwind CSS, Vite, PWA, FastAPI, SQLAlchemy, PostgreSQL, "
        "Supabase, Firebase, Electron, Tauri, Tkinter, discord.js, Netlify, Render, GitHub Actions e Git.",
        "".join(css),
        corpo,
    )


# --------------------------------------------------------------------------------------------
# 4. Créditos finais
# --------------------------------------------------------------------------------------------
CREDITOS = [
    ("REALIZAÇÃO", "Thiago Anjos", None),
    ("ARGUMENTO E CÓDIGO", "Thiago Anjos", None),
    ("ESTÚDIO", "LisFilms", "verde"),
    ("SEGURANÇA", "LisSecurity", "verde"),
    ("COMUNIDADE", "LisDiscord", "discord2"),
    ("INTERFACE", "React · TypeScript · Tailwind", None),
    ("BASTIDORES", "FastAPI · PostgreSQL", None),
    ("COFRE-FORTE", "Rust · Tauri", None),
    ("FORMAÇÃO", "TeSP Web e Multimédia", None),
    ("RODADO EM", "Leiria, Portugal", None),
    ("COM RAÍZES EM", "Mogi das Cruzes, Brasil", None),
    ("UM OBRIGADO", "a quem viu até ao fim", "verde"),
]


def creditos() -> str:
    W, H = 860, 250
    cx = W / 2
    css = []
    defs = [DEFS_COMUNS]
    defs.append(
        '<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".22" stop-color="#fff"/><stop offset=".78" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="janela"><rect x="40" y="70" width="{W - 80}" height="138" fill="url(#fade)"/></mask>'
        f'<clipPath id="forma"><rect width="{W}" height="{H}" rx="22"/></clipPath>'
    )
    defs.append(radial("luzCreditos", C["verde"], 0.12))
    passo = 30
    lista = []
    for k in range(2):
        for i, (papel, nome, cor) in enumerate(CREDITOS):
            y = 98 + (k * len(CREDITOS) + i) * passo
            fill = C[cor] if cor else C["texto"]
            lista.append(texto(cx - 14, y, esc(papel), 9.5, 700, C["tenue"], "end", 2.2))
            lista.append(texto(cx + 14, y + 0.5, esc(nome), 15, 700, fill))
    alt = len(CREDITOS) * passo
    css.append(f"@keyframes rolar{{from{{transform:translateY(0);}}to{{transform:translateY(-{alt}px);}}}}")
    p = [f'<rect width="{W}" height="{H}" fill="{C["lateral"]}"/>', f'<ellipse cx="{cx}" cy="130" rx="360" ry="120" fill="url(#luzCreditos)"/>']
    # películas laterais
    css.append("@keyframes descer{from{transform:translateY(-18px);}to{transform:translateY(0);}}")
    for x0 in (0, W - 30):
        furos = "".join(f'<rect x="{x0 + 11}" y="{y}" width="8" height="10" rx="2" fill="{C["cartao2"]}"/>' for y in range(-18, H + 18, 18))
        p.append(f'<rect x="{x0}" width="30" height="{H}" fill="{C["bg"]}"/><g style="animation:descer 1.2s linear infinite">{furos}</g>')
    p.append(marca_lis(cx - 13, 22, 1, brilho=False))
    p.append(texto(cx, 60, "CRÉDITOS FINAIS", 9.5, 800, C["suave"], "middle", 4))
    p.append(f'<g mask="url(#janela)"><g style="animation:rolar {len(CREDITOS) * 2.6:.1f}s linear infinite">{"".join(lista)}</g></g>')
    p.append(f'<line x1="{cx - 120}" y1="216" x2="{cx + 120}" y2="216" stroke="{C["borda"]}"/>')
    p.append(texto(cx, 236, f'Obrigado pela visita <tspan fill="{C["verde"]}">·</tspan> lisfilms.pt', 11.5, 600, C["suave"], "middle"))
    corpo = (
        f"<defs>{''.join(defs)}</defs>"
        f'<g clip-path="url(#forma)">{"".join(p)}</g>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{C["borda"]}"/>'
    )
    return documento(
        W,
        H,
        "Créditos finais",
        "Créditos a rolar como no fim de um filme: realização e código de Thiago Anjos, estúdio LisFilms, "
        "segurança LisSecurity, comunidade LisDiscord.",
        "".join(css),
        corpo,
    )


# --------------------------------------------------------------------------------------------
# 5. Estatísticas reais (GitHub GraphQL)
# --------------------------------------------------------------------------------------------
CONSULTA = """
query($login: String!) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        isPrivate
        stargazerCount
        languages(first: 15, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}
"""


def obter_dados(token: str) -> dict:
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": UTILIZADOR}}).encode()
    pedido = urllib.request.Request(
        "https://api.github.com/graphql",
        data=corpo,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "perfil-thiagodanjos"},
    )
    with urllib.request.urlopen(pedido, timeout=30) as resp:
        resposta = json.load(resp)
    if resposta.get("errors"):
        raise RuntimeError("; ".join(e.get("message", "?") for e in resposta["errors"]))
    u = resposta["data"]["user"]
    repos = u["repositories"]["nodes"]
    linguagens: dict[str, list] = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            nome = e["node"]["name"]
            atual = linguagens.setdefault(nome, [0, e["node"]["color"] or C["tenue"]])
            atual[0] += e["size"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    dias = [
        {"data": d["date"], "n": d["contributionCount"], "nivel": d["contributionLevel"]}
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]
    return {
        "exemplo": False,
        "total": cal["totalContributions"],
        "dias": dias,
        "publicos": sum(1 for r in repos if not r["isPrivate"]),
        "estrelas": sum(r["stargazerCount"] for r in repos if not r["isPrivate"]),
        "seguidores": u["followers"]["totalCount"],
        "desde": u["createdAt"][:4],
        "linguagens": linguagens,
    }


def dados_exemplo() -> dict:
    r = random.Random(2026)
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=364 + (hoje.weekday() + 1) % 7)
    dias = []
    d = inicio
    while d <= hoje:
        base = 0 if r.random() < 0.35 else int(r.expovariate(1 / 4)) + 1
        dias.append({"data": d.isoformat(), "n": base, "nivel": None})
        d += dt.timedelta(days=1)
    return {
        "exemplo": True,
        "total": sum(x["n"] for x in dias),
        "dias": dias,
        "publicos": 4,
        "estrelas": 3,
        "seguidores": 12,
        "desde": "2021",
        "linguagens": {
            "TypeScript": [520, "#3178c6"],
            "Python": [410, "#3572A5"],
            "Rust": [160, "#dea584"],
            "JavaScript": [120, "#f1e05a"],
            "CSS": [60, "#663399"],
            "HTML": [20, "#e34c26"],
        },
    }


NIVEIS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
CORES_NIVEL = ["#1a1f26", "#123d24", "#167a3c", "#1aae52", "#1ed760"]


def nivel(dia: dict, maximo: int) -> int:
    if dia.get("nivel") in NIVEIS:
        return NIVEIS[dia["nivel"]]
    if dia["n"] == 0:
        return 0
    return min(4, 1 + int(3 * dia["n"] / max(1, maximo)))


def sequencias(dias: list[dict]) -> tuple[int, int]:
    melhor = corrida = 0
    for d in dias:
        corrida = corrida + 1 if d["n"] > 0 else 0
        melhor = max(melhor, corrida)
    atual = 0
    lista = list(dias)
    if lista and lista[-1]["n"] == 0:
        lista = lista[:-1]  # hoje ainda pode vir a ter contribuições
    for d in reversed(lista):
        if d["n"] == 0:
            break
        atual += 1
    return atual, melhor


def fmt(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def dias_txt(v: int) -> str:
    return f"{v} {'dia' if v == 1 else 'dias'}"


def percentagem(p: float) -> str:
    """Uma casa decimal, sem arredondar para 100 % nem para 0 % quando não é verdade."""
    if p < 0.1:
        return "<0,1%"
    if p >= 100:
        return "100%"
    if p > 99.9:
        return ">99,9%"
    v = math.floor(p * 10) / 10 if p > 99 else round(p, 1)
    return f"{v:.1f}%".replace(".", ",")


def estatisticas(dados: dict) -> str:
    W, H = 860, 556
    css = []
    defs = [DEFS_COMUNS]
    p = []
    dias = dados["dias"]
    hoje = dt.date.fromisoformat(dias[-1]["data"]) if dias else dt.date.today()
    atual, melhor = sequencias(dias)
    por_dia = [0] * 7
    for d in dias:
        por_dia[dt.date.fromisoformat(d["data"]).weekday()] += d["n"]
    dia_top = max(range(7), key=lambda i: por_dia[i]) if any(por_dia) else 0

    # cabeçalho
    p.append(f'<rect x="28" y="30" width="4" height="22" rx="2" fill="{C["verde"]}"/>')
    p.append(texto(42, 47, "Visão geral", 17, 800, C["texto"]))
    p.append(
        texto(W - 28, 47, f"Atualizado a {hoje.day} {MESES[hoje.month - 1]} {hoje.year} · dados do GitHub", 10.5, 500, C["tenue"], "end")
    )
    if dados["exemplo"]:
        p.append(f'<rect x="{W / 2 - 92}" y="28" width="184" height="24" rx="12" fill="#2b0f12" stroke="{C["perigo"]}"/>')
        p.append(texto(W / 2, 44, "DADOS DE EXEMPLO", 10, 800, C["perigo"], "middle", 2))

    # cartões
    cartoes = [
        ("git-commit-horizontal", fmt(dados["total"]), "Contribuições", "nos últimos 12 meses"),
        (
            ("flame", dias_txt(atual), "Sequência atual", f"melhor: {dias_txt(melhor)}")
            if atual
            else ("flame", dias_txt(melhor), "Melhor sequência", "dias seguidos a contribuir")
        ),
        ("folder-git-2", fmt(dados["publicos"]), "Repositórios públicos", f"{fmt(dados['estrelas'])} {'estrela' if dados['estrelas'] == 1 else 'estrelas'}"),
        ("users", fmt(dados["seguidores"]), "Seguidores", f"no GitHub desde {dados['desde']}"),
    ]
    cw = (W - 56 - 3 * 12) / 4
    for i, (ic, num, rot, sub) in enumerate(cartoes):
        x = 28 + i * (cw + 12)
        y = 72
        p.append(
            f'<g style="animation:surgir .7s cubic-bezier(.22,1,.36,1) {0.1 + i * 0.1:.2f}s both">'
            f'<rect x="{n(x)}" y="{y}" width="{n(cw)}" height="100" rx="14" fill="{C["cartao"]}" stroke="{C["borda"]}"/>'
            f'<rect x="{n(x + 16)}" y="{y + 16}" width="36" height="36" rx="10" fill="{C["verde_suave"]}"/>'
            + icone(ic, x + 25, y + 25, 18, C["verde"])
            + texto(x + 64, y + 44, esc(num), 25, 900, C["texto"])
            + texto(x + 16, y + 74, esc(rot), 11.5, 600, C["suave"])
            + texto(x + 16, y + 89, esc(sub), 10, 500, C["tenue"])
            + "</g>"
        )

    # linha do tempo (calendário)
    yc = 188
    p.append(f'<rect x="28" y="{yc}" width="{W - 56}" height="180" rx="14" fill="{C["cartao"]}" stroke="{C["borda"]}"/>')
    p.append(texto(44, yc + 26, "Um ano em cena", 13, 800, C["texto"]))
    p.append(texto(W - 44, yc + 26, f"{fmt(dados['total'])} contribuições · a última coluna é esta semana", 10.5, 500, C["tenue"], "end"))
    semanas: list[list[dict]] = []
    for d in dias:
        dd = dt.date.fromisoformat(d["data"])
        linha = (dd.weekday() + 1) % 7  # domingo = 0, como no GitHub
        if not semanas or linha == 0:
            semanas.append([None] * 7)  # type: ignore[list-item]
        semanas[-1][linha] = d
    semanas = semanas[-53:]
    maximo = max((d["n"] for d in dias), default=1)
    x0, y0, passo, lado = 72, yc + 56, 14, 11
    inicios = []  # (coluna, mês) onde cada mês começa
    for c, sem in enumerate(semanas):
        primeiro = next((d for d in sem if d), None)
        if primeiro:
            mes = dt.date.fromisoformat(primeiro["data"]).month
            if not inicios or inicios[-1][1] != mes:
                inicios.append((c, mes))
    if len(inicios) > 1 and inicios[1][0] - inicios[0][0] < 3:
        inicios.pop(0)  # o primeiro mês só aparece em uma ou duas colunas
    for c, mes in inicios:
        p.append(texto(x0 + c * passo, y0 - 8, MESES[mes - 1], 9.5, 500, C["tenue"]))
    celulas = []
    for c, sem in enumerate(semanas):
        x = x0 + c * passo
        col = []
        for li, d in enumerate(sem):
            if d is None:
                continue
            col.append(f'<rect x="{x}" y="{y0 + li * passo}" width="{lado}" height="{lado}" rx="2.5" fill="{CORES_NIVEL[nivel(d, maximo)]}"/>')
        celulas.append(f'<g style="animation:aparecer .5s ease-out {0.3 + c * 0.018:.3f}s both">{"".join(col)}</g>')
    for li, rot in ((1, "seg"), (3, "qua"), (5, "sex")):
        p.append(texto(x0 - 8, y0 + li * passo + 9, rot, 9, 500, C["tenue"], "end"))
    p.append("".join(celulas))
    # cabeça de leitura a passar pelo ano (como a barra de um vídeo)
    largura_grade = len(semanas) * passo
    ciclo = 9.0
    css.append(
        f"@keyframes cabeca{{from{{transform:translateX(0);}}to{{transform:translateX({largura_grade}px);}}}}"
        "@keyframes passa{0%{opacity:0;}1.2%{opacity:.32;}3.6%{opacity:0;}100%{opacity:0;}}"
    )
    defs.append(
        '<linearGradient id="rasto" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1ed760" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#1ed760" stop-opacity=".22"/></linearGradient>'
    )
    brilhos = []
    for c in range(len(semanas)):
        atraso = c * passo / largura_grade * ciclo - 0.012 * ciclo
        brilhos.append(
            f'<rect x="{x0 + c * passo - 1}" y="{y0 - 1}" width="{lado + 2}" height="{7 * passo - 1}" rx="3" fill="#ffffff" opacity="0" '
            f'style="animation:passa {ciclo}s linear {atraso:.3f}s infinite"/>'
        )
    p.append("".join(brilhos))
    p.append(
        f'<g style="animation:cabeca {ciclo}s linear infinite"><rect x="{x0 - 40}" y="{y0 - 4}" width="38" height="{7 * passo + 5}" fill="url(#rasto)"/>'
        f'<rect x="{x0 - 3}" y="{y0 - 6}" width="2" height="{7 * passo + 9}" rx="1" fill="{C["verde"]}"/>'
        f'<circle cx="{x0 - 2}" cy="{y0 - 7}" r="3.5" fill="{C["verde"]}"/></g>'
    )
    ly = y0 + 7 * passo + 14
    p.append(texto(44, ly + 9, f"Dia com mais contribuições: {max_dia_txt(dias)}", 10, 500, C["tenue"]))
    lx = W - 44 - (5 * 14) - 34
    p.append(texto(lx - 8, ly + 9, "menos", 9.5, 500, C["tenue"], "end"))
    for i, cor in enumerate(CORES_NIVEL):
        p.append(f'<rect x="{lx + i * 14}" y="{ly}" width="11" height="11" rx="2.5" fill="{cor}"/>')
    p.append(texto(lx + 5 * 14 + 3, ly + 9, "mais", 9.5, 500, C["tenue"]))

    # linguagens
    yl = 384
    wl = 520
    p.append(f'<rect x="28" y="{yl}" width="{wl}" height="140" rx="14" fill="{C["cartao"]}" stroke="{C["borda"]}"/>')
    p.append(texto(44, yl + 26, "Linguagens", 13, 800, C["texto"]))
    p.append(texto(28 + wl - 16, yl + 26, "por tamanho do código", 10.5, 500, C["tenue"], "end"))
    lings = sorted(dados["linguagens"].items(), key=lambda kv: -kv[1][0])
    soma = sum(v[0] for _, v in lings) or 1
    topo = lings[:6]
    resto = sum(v[0] for _, v in lings[6:])
    if resto:
        topo = topo[:5] + [("Outras", [resto + topo[5][1][0], C["tenue"]])]
    bx, bw = 44, wl - 32
    x = bx
    segs = []
    for i, (nome, (tam, cor)) in enumerate(topo):
        w = bw * tam / soma
        segs.append(
            f'<rect class="fe" x="{n(x)}" y="{yl + 42}" width="{n(max(w - 2, 1.5))}" height="10" rx="3" fill="{cor}" '
            f'style="animation:esticar .9s cubic-bezier(.22,1,.36,1) {0.5 + i * 0.12:.2f}s both"/>'
        )
        x += w
    css.append("@keyframes esticar{from{transform:scaleX(0);}to{transform:scaleX(1);}}")
    p.append(f'<rect x="{bx}" y="{yl + 42}" width="{bw}" height="10" rx="3" fill="{C["cartao2"]}"/>' + "".join(segs))
    for i, (nome, (tam, cor)) in enumerate(topo):
        col, lin = i % 3, i // 3
        lx2 = bx + col * (bw / 3)
        ly2 = yl + 82 + lin * 28
        pct_txt = percentagem(100 * tam / soma)
        p.append(
            f'<g style="animation:aparecer .6s ease-out {0.8 + i * 0.08:.2f}s both">'
            f'<circle cx="{n(lx2 + 5)}" cy="{ly2 - 4}" r="5" fill="{cor}"/>'
            + texto(lx2 + 16, ly2, esc(nome), 11.5, 700, C["texto"])
            + texto(lx2 + 16 + FONTE.largura(nome, 11.5, 700) + 6, ly2, esc(pct_txt), 10.5, 500, C["tenue"])
            + "</g>"
        )

    # ritmo semanal
    xr = 28 + wl + 12
    wr = W - 28 - xr
    p.append(f'<rect x="{xr}" y="{yl}" width="{wr}" height="140" rx="14" fill="{C["cartao"]}" stroke="{C["borda"]}"/>')
    p.append(texto(xr + 16, yl + 26, "Ritmo semanal", 13, 800, C["texto"]))
    p.append(texto(xr + wr - 16, yl + 26, f"mais ativo: {DIAS_LONGOS[dia_top]}", 10.5, 500, C["tenue"], "end"))
    maxd = max(por_dia) or 1
    bwid, gap = 20, (wr - 32 - 7 * 20) / 6
    base = yl + 112
    for i in range(7):
        hb = max(3, 60 * por_dia[i] / maxd)
        bx2 = xr + 16 + i * (bwid + gap)
        cor = C["verde"] if i == dia_top else "#2a3a31"
        p.append(
            f'<rect class="fbase" x="{n(bx2)}" y="{n(base - hb)}" width="{bwid}" height="{n(hb)}" rx="5" fill="{cor}" '
            f'style="animation:subirBarra .9s cubic-bezier(.22,1,.36,1) {0.6 + i * 0.08:.2f}s both"/>'
        )
        p.append(texto(bx2 + bwid / 2, base + 16, DIAS[i], 9.5, 600 if i == dia_top else 500, C["texto"] if i == dia_top else C["tenue"], "middle"))
    css.append("@keyframes subirBarra{from{transform:scaleY(0);}to{transform:scaleY(1);}}")

    p.append(
        texto(W / 2, H - 14, "Gerado todos os dias pelo GitHub Actions deste repositório (scripts/perfil.py)", 9.5, 500, C["tenue"], "middle")
    )
    corpo = (
        f"<defs>{''.join(defs)}</defs>"
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="{C["bg"]}" stroke="{C["borda"]}"/>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="url(#pontos)"/>' + "".join(p)
    )
    return documento(
        W,
        H,
        "Estatísticas do GitHub",
        f"{fmt(dados['total'])} contribuições nos últimos 12 meses; sequência atual de {dias_txt(atual)} (melhor: {dias_txt(melhor)}); "
        f"{dados['publicos']} repositórios públicos; {dados['seguidores']} seguidores; "
        f"linguagens: {', '.join(nome for nome, _ in topo)}.",
        "".join(css),
        corpo,
    )


def max_dia_txt(dias: list[dict]) -> str:
    if not dias or max(d["n"] for d in dias) == 0:
        return "—"
    d = max(dias, key=lambda x: (x["n"], x["data"]))
    data = dt.date.fromisoformat(d["data"])
    return f"{data.day} {MESES[data.month - 1]} ({d['n']})"


# --------------------------------------------------------------------------------------------
def gravar(nome: str, svg: str, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(svg, encoding="utf-8")
    print(f"{nome}: {len(svg.encode()) / 1024:.1f} KB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exemplo", action="store_true", help="estatísticas com dados de exemplo (pré-visualização)")
    ap.add_argument("--so-estaticas", action="store_true", help="não gera as estatísticas")
    ap.add_argument("--saida", type=Path, default=SAIDA, help="pasta de saída (por omissão: assets/)")
    a = ap.parse_args()

    gravar("abertura.svg", abertura(), a.saida)
    for i, chave in enumerate(CARTAZES):
        gravar(f"cartaz-{chave}.svg", cartaz(chave, i * 0.15), a.saida)
    gravar("tecnologias.svg", tecnologias(), a.saida)
    gravar("creditos.svg", creditos(), a.saida)
    if a.so_estaticas:
        return 0
    if a.exemplo:
        gravar("estatisticas.svg", estatisticas(dados_exemplo()), a.saida)
        return 0
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("sem GITHUB_TOKEN: as estatísticas não foram atualizadas (usa --exemplo para pré-visualizar)", file=sys.stderr)
        return 1
    try:
        dados = obter_dados(token)
    except Exception as e:  # a imagem anterior fica como estava
        print(f"erro ao obter as estatísticas: {e}", file=sys.stderr)
        return 1
    gravar("estatisticas.svg", estatisticas(dados), a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
