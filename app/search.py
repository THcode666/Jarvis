# -*- coding: utf-8 -*-
"""全局搜索引擎：模糊搜索 + 关联搜索 + 拼音搜索。

- 模糊搜索：忽略大小写/首尾空格；支持空格分隔多关键词（全部命中排名更靠前）。
- 关联搜索：跨四个模块、跨所有字段（描述/难点/内容/解决方案/SOP正文/附件名/PPT文字）；
  只要命中任一关键词即返回，按命中率打分排序；整句命中得分最高。
- 拼音搜索：纯字母关键词可命中中文的拼音首字母（hzk → 换针卡）或全拼（zhenka），
  得分低于直接命中；未安装 pypinyin 时该能力自动关闭，不影响其他搜索。
- 标题类字段命中额外加权，让"看起来最相关"的结果排在最前。

各模块只需提供 search_records()，返回统一结构，新增模块无需改动本文件。
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass
class SearchRecord:
    module_key: str      # tasks / memos / questions / sops
    module_name: str     # 缓急 / 帮记 / 解惑 / 存知
    item_id: str
    title: str           # 结果卡片主标题
    fields: dict = field(default_factory=dict)  # {字段名: 文本}，均参与搜索
    time_text: str = ""  # 卡片上显示的时间


@dataclass
class SearchResult:
    record: SearchRecord
    score: float
    snippet_html: str    # 带高亮的摘要（rich text，可直接显示）
    via_pinyin: bool = False   # 是否有关键词是靠拼音命中的


def _norm(s: str) -> str:
    return (s or "").lower().strip()


# ---- 拼音形式（首字母串 / 全拼串），按文本缓存 ----

_lazy_pinyin = None


def _pinyin_fn():
    global _lazy_pinyin
    if _lazy_pinyin is None:
        try:
            from pypinyin import lazy_pinyin
            _lazy_pinyin = lazy_pinyin
        except ImportError:
            _lazy_pinyin = False
    return _lazy_pinyin or None


@lru_cache(maxsize=8192)
def pinyin_forms(text: str) -> tuple:
    """返回 (首字母串, 全拼串)，小写；无拼音库或无汉字时返回 ("", "")。"""
    fn = _pinyin_fn()
    if not fn or not text:
        return "", ""
    try:
        segs = [s for s in fn(text) if s]
        init = "".join(s[0] for s in segs if s[0].isascii() and s[0].isalpha()).lower()
        full = "".join(ch for ch in "".join(segs).lower()
                       if ch.isascii() and ch.isalpha())
        return init, full
    except Exception:
        return "", ""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _highlight(escaped: str, token: str) -> str:
    """在已转义的文本上做大小写不敏感的命中高亮。"""
    if not token:
        return escaped
    pattern = re.compile(re.escape(_escape(token)), re.IGNORECASE)
    return pattern.sub(lambda m: f"<font color='#ffd166'><b>{m.group(0)}</b></font>", escaped)


def _snippet_html(fields: dict, tokens: list, phrase: str, radius: int = 30) -> str:
    """选第一个命中的字段截取一段摘要，并对命中词加高亮。"""
    joined = {name: text for name, text in fields.items() if text}
    if not joined:
        return ""

    text = next(iter(joined.values()))
    lower = _norm(text)
    pos = -1
    if phrase:
        pos = lower.find(phrase)
    if pos < 0:
        for t in tokens:
            pos = lower.find(t)
            if pos >= 0:
                break
    if pos < 0:
        snippet = text[: radius * 2] + ("…" if len(text) > radius * 2 else "")
    else:
        needle_len = len(phrase) if pos == lower.find(phrase) and phrase else len(tokens[0])
        start = max(0, pos - radius // 2)
        end = min(len(text), pos + needle_len + radius)
        snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")

    result = _escape(snippet)
    for t in sorted({t for t in [*tokens, phrase] if t}, key=len, reverse=True):
        result = _highlight(result, t)
    return result


def search(records: list, query: str) -> list:
    """在记录列表中搜索，返回按相关度排序的 SearchResult 列表。"""
    query = _norm(query)
    if not query:
        return []
    tokens = [t for t in query.split() if t]
    if not tokens:
        return []
    phrase = " ".join(tokens)

    results = []
    for rec in records:
        texts = {name: _norm(text) for name, text in rec.fields.items() if text}
        if not texts:
            continue
        combined = " ".join(texts.values())
        title_l = _norm(rec.title)

        # 该记录所有字段的拼音形式（缓存后开销很小）
        inits, fulls = [], []
        for text in rec.fields.values():
            if text:
                i, f = pinyin_forms(text)
                if i:
                    inits.append(i)
                if f:
                    fulls.append(f)
        all_init = " ".join(inits)
        all_full = " ".join(fulls)

        def direct(t):
            return t in combined

        def by_pinyin(t):
            # 纯字母、至少2位才参与拼音匹配，避免单字母噪声
            return len(t) >= 2 and t.isascii() and (t in all_init or t in all_full)

        score = 0.0
        via_py = False
        if phrase in combined:
            score = 100.0
            if phrase in title_l:
                score += 60.0
        elif all(direct(t) for t in tokens):
            score = 70.0
            if all(t in title_l for t in tokens):
                score += 30.0
        elif all(direct(t) or by_pinyin(t) for t in tokens):
            score = 55.0
            via_py = any(not direct(t) for t in tokens)
        else:
            d_hit = sum(1 for t in tokens if direct(t))
            p_hit = sum(1 for t in tokens if not direct(t) and by_pinyin(t))
            if d_hit:
                score = 40.0 * (d_hit + p_hit) / len(tokens)
                via_py = p_hit > 0
            elif p_hit:
                score = 22.0 * p_hit / len(tokens)
                via_py = True

        if score <= 0:
            continue
        results.append(SearchResult(
            rec, score, _snippet_html(rec.fields, tokens, phrase), via_py))

    results.sort(key=lambda r: (-r.score, r.record.module_key, r.record.title))
    return results
