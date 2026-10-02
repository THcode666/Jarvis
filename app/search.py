# -*- coding: utf-8 -*-
"""全局搜索引擎：模糊搜索 + 关联搜索。

- 模糊搜索：忽略大小写/首尾空格；支持空格分隔多关键词（全部命中排名更靠前）。
- 关联搜索：跨四个模块、跨所有字段（描述/难点/内容/解决方案/SOP正文/附件名/PPT文字）；
  只要命中任一关键词即返回，按命中率打分排序；整句命中得分最高。
- 标题类字段命中额外加权，让"看起来最相关"的结果排在最前。

各模块只需提供 search_records()，返回统一结构，新增模块无需改动本文件。
"""
import re
from dataclasses import dataclass, field


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


def _norm(s: str) -> str:
    return (s or "").lower().strip()


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

        score = 0.0
        # 1) 整句命中（模糊搜索核心）
        if phrase in combined:
            score = 100.0
            if phrase in title_l:
                score += 60.0
        # 2) 全部关键词命中（可分散在不同字段——跨字段"关联"）
        elif all(t in combined for t in tokens):
            score = 70.0
            if all(t in title_l for t in tokens):
                score += 30.0
        # 3) 部分关键词命中（宽松关联，保证"搜得到"）
        else:
            hit = sum(1 for t in tokens if t in combined)
            if hit:
                score = 40.0 * hit / len(tokens)

        if score <= 0:
            continue
        results.append(SearchResult(rec, score, _snippet_html(rec.fields, tokens, phrase)))

    results.sort(key=lambda r: (-r.score, r.record.module_key, r.record.title))
    return results
