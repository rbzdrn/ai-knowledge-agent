# import pytest
# from typing import List
#
#
# class TextChunker:
#     """Split text into overlapping chunks for embedding and retrieval."""
#
#     def __init__(
#         self,
#         chunk_size: int | None = None,
#         chunk_overlap: int | None = None,
#     ):
#         self.chunk_size = chunk_size or 50
#         self.chunk_overlap = chunk_overlap or 10
#         if self.chunk_overlap >= self.chunk_size:
#             raise ValueError("chunk_overlap must be less than chunk_size")
#
#         self._separators = [
#             "\n\n", "\n", "。", ". ", ".", "；", ";", "！", "!", "？", "?", " ", ""
#         ]
#
#     def split(self, text: str) -> List[str]:
#         return self._split_recursive(text, self._separators)
#
#     def split_with_metadata(self, text: str, base_metadata: dict) -> List[dict]:
#         """Split and return chunks with per-chunk metadata."""
#         chunks = self.split(text)
#         results = []
#         for i, chunk in enumerate(chunks):
#             meta = dict(base_metadata)
#             meta["chunk_index"] = i
#             meta["chunk_count"] = len(chunks)
#             results.append({"text": chunk, "metadata": meta})
#         return results
#
#     def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
#         chunks = []
#         separator = separators[0]
#         next_separators = separators[1:] if len(separators) > 1 else [""]
#
#         if not separator:
#             # Final fallback: split by fixed chunk_size
#             return self._split_by_length(text)
#
#         splits = text.split(separator)
#         current = ""
#         for part in splits:
#             candidate = current + (separator if current else "") + part
#             if len(candidate) <= self.chunk_size:
#                 current = candidate
#             else:
#                 if current:
#                     chunks.append(current.strip())
#                 if len(part) > self.chunk_size:
#                     sub_chunks = self._split_recursive(part, next_separators)
#                     if chunks and self.chunk_overlap > 0:
#                         last = chunks[-1]
#                         overlap_text = last[-self.chunk_overlap:]
#                         if sub_chunks:
#                             sub_chunks[0] = overlap_text + sub_chunks[0]
#                     chunks.extend(sub_chunks)
#                     current = ""
#                 else:
#                     current = part
#
#         if current.strip():
#             chunks.append(current.strip())
#
#         # Merge short chunks
#         return self._merge_short(chunks)
#
#     def _split_by_length(self, text: str) -> List[str]:
#         chunks = []
#         start = 0
#         while start < len(text):
#             end = min(start + self.chunk_size, len(text))
#             chunks.append(text[start:end].strip())
#             start = end - self.chunk_overlap
#             if start >= len(text):
#                 break
#             if start < 0:
#                 start = 0
#         return [c for c in chunks if c]
#
#     def _merge_short(self, chunks: List[str], min_len: int = 50) -> List[str]:
#         if not chunks:
#             return chunks
#         merged = []
#         for chunk in chunks:
#             if len(chunk) < min_len and merged:
#                 merged[-1] = merged[-1] + " " + chunk
#             else:
#                 merged.append(chunk)
#         return merged
#
#
# # ===================== 以下是 pytest 测试用例 =====================
#
# class TestTextChunkerInit:
#     """测试初始化参数校验"""
#
#     def test_default_params(self):
#         chunker = TextChunker()
#         assert chunker.chunk_size == 50
#         assert chunker.chunk_overlap == 10
#
#     def test_custom_params(self):
#         chunker = TextChunker(chunk_size=100, chunk_overlap=20)
#         assert chunker.chunk_size == 100
#         assert chunker.chunk_overlap == 20
#
#     def test_overlap_equal_size_raise_error(self):
#         with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
#             TextChunker(chunk_size=50, chunk_overlap=50)
#
#     def test_overlap_greater_size_raise_error(self):
#         with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
#             TextChunker(chunk_size=50, chunk_overlap=60)
#
#
# class TestTextChunkerSplit:
#     """测试核心 split 切块逻辑"""
#
#     def test_empty_text_returns_empty_list(self):
#         chunker = TextChunker(chunk_size=50, chunk_overlap=10)
#         assert chunker.split("") == []
#
#     def test_short_text_no_split(self):
#         """文本长度小于 chunk_size，直接返回单块"""
#         chunker = TextChunker(chunk_size=50, chunk_overlap=10)
#         text = "这是一段很短的测试文本。"
#         result = chunker.split(text)
#         assert len(result) == 1
#         assert result[0] == text.strip()
#
#     def test_normal_chinese_recursive_split_count(self):
#         """正常中文文本触发递归降级，切块数量符合预期"""
#         text = """人工智能是计算机科学的一个重要分支领域。它致力于研究如何让机器模拟人类的智能行为，包括学习、推理、感知等能力。
# 自然语言处理是人工智能的核心子领域之一。它专注于研究计算机与人类语言之间的交互方式，让机器能够理解和生成自然语言。
# 文本切块是自然语言处理中的基础操作。"""
#         chunker = TextChunker(chunk_size=50, chunk_overlap=10)
#         result = chunker.split(text)
#         # 验证至少切出2块，触发了递归切割
#         assert len(result) >= 2
#         # 验证所有块非空
#         assert all(len(chunk) > 0 for chunk in result)
#
#     def test_overlap_exists_between_recursive_chunks(self):
#         """递归切割场景下，相邻块存在指定长度的重叠内容"""
#         text = "一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十。一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十。"
#         chunker = TextChunker(chunk_size=30, chunk_overlap=10)
#         result = chunker.split(text)
#         if len(result) >= 2:
#             # 后一块的开头包含前一块末尾的重叠内容
#             last_end = result[-2][-10:]
#             assert last_end in result[-1]
#
#     def test_no_punctuation_fallback_hard_split(self):
#         """无标点无分隔符文本，兜底进入硬切逻辑"""
#         text = "一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十"
#         chunker = TextChunker(chunk_size=20, chunk_overlap=5)
#         result = chunker.split(text)
#         # 硬切至少产出多块
#         assert len(result) >= 2
#         # 硬切场景下块间存在重叠
#         assert result[0][-5:] == result[1][:5]
#
#     def test_merge_short_chunks_effect(self):
#         """短块合并逻辑生效：小于50字符的块会被合并到前一块"""
#         # 构造：一个长句 + 一个极短句，验证短句会被合并
#         text = "这是一个长度足够长的句子，用来测试短块合并的功能是否正常生效。短句。"
#         chunker = TextChunker(chunk_size=60, chunk_overlap=5)
#         result = chunker.split(text)
#         # 最终只有1块，说明短句被合并
#         assert len(result) == 1
#         assert "短句" in result[0]
#
#     def test_separator_priority_paragraph_first(self):
#         """分隔符优先级：优先按段落 \n\n 切割，再降级到句号"""
#         text = "第一段内容。第一句。第二句。\n\n第二段内容。第三句。第四句。"
#         chunker = TextChunker(chunk_size=50, chunk_overlap=5)
#         result = chunker.split(text)
#         # 段落分隔优先，两段内容会被优先分开
#         assert len(result) >= 2
#         assert "第一段" in result[0]
#         assert "第二段" in result[-1]
#
#     @pytest.mark.skip(reason="原始代码存在死循环bug，运行会卡死，仅用于验证bug存在")
#     def test_hard_split_infinite_loop_bug(self):
#         """验证硬切边界bug：文本长度小于chunk_size时会无限循环"""
#         text = "一二三四五六七八九十"  # 长度10
#         chunker = TextChunker(chunk_size=20, chunk_overlap=10)
#         # 原始代码执行到这里会陷入死循环
#         result = chunker.split(text)
#         assert len(result) == 1
#
#
# class TestSplitWithMetadata:
#     """测试元数据附加功能"""
#
#     def test_metadata_fields_correct(self):
#         text = "测试文本。"
#         chunker = TextChunker(chunk_size=50, chunk_overlap=10)
#         base_meta = {"doc_id": "doc_001", "source": "测试文档"}
#         result = chunker.split_with_metadata(text, base_meta)
#
#         assert len(result) == 1
#         item = result[0]
#         assert "text" in item
#         assert "metadata" in item
#         assert item["metadata"]["doc_id"] == "doc_001"
#         assert item["metadata"]["source"] == "测试文档"
#         assert item["metadata"]["chunk_index"] == 0
#         assert item["metadata"]["chunk_count"] == 1
#
#     def test_metadata_chunk_index_count(self):
#         text = "一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十"
#         chunker = TextChunker(chunk_size=20, chunk_overlap=5)
#         result = chunker.split_with_metadata(text, {})
#
#         chunk_count = len(result)
#         for i, item in enumerate(result):
#             assert item["metadata"]["chunk_index"] == i
#             assert item["metadata"]["chunk_count"] == chunk_count

#
# list = [
#     "人工智能是计算机科学的一个分支",
#     "机器学习是人工智能的子领域",
#     "深度学习使用神经网络"
# ]
#
# for idx,text in enumerate(list):
#     print(idx,text)
doc_tokens = ["人工智能是计算机科学的一个分支"]
tf = {}
for t in doc_tokens:
    print(t)
    tf[t] = tf.get(t, 0) + 1
    print(tf)
print(tf)