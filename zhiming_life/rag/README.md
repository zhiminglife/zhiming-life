# rag/ —— 终端版兼容接口

终端教学版保留轻量的 RAG 接缝：师傅解读前会调用 `retrieve()` 获取参考资料，默认返回空字符串。需要给终端版接入自己的语料时，可以在 `retriever.py` 的接口上扩展。

桌面版使用 `zhiming_life/desktop_api/library.py` 中的正式 RAG 实现：

- 知识库与匿名命例库使用两个物理 SQLite 文件；
- FastEmbed / ONNX 生成向量；
- sqlite-vec 执行向量检索；
- 本地 reranker 对召回结果重新排序；
- 咨询时把实际命中的依据传给八字解读。

## 一个前提：命例只触发联想，不作判决

引用命例时应参考多个来源，每个只取最相关的小点，不把别人的结论整体套用到当前命主。参考资料用于提供线索，不能替代现实信息和用户确认。

---

<sub>[zhiming.life](https://zhiming.life)</sub>
