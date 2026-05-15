export interface MechanicalAnalysisResult {
  partType?: string;
  material?: string;
  heatTreatment?: string;

  keyDimensions?: string[];
  tolerances?: string[];
  datums?: string[];
  roughness?: string[];

  features?: string[];
  threads?: string[];
  sections?: string[];

  processes?: string[];

  feature_id?: string[];
  feature_type?: string[];
  relation?: string[];
  process_semantic?: string[];

  rawMarkdown?: string;
}

function uniq(items: string[], limit = 30): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of items) {
    const one = String(raw || '').replace(/\s+/g, ' ').trim();
    if (!one) continue;
    const key = one.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(one);
    if (out.length >= limit) break;
  }
  return out;
}

function pickFirst(markdown: string, patterns: RegExp[]): string | undefined {
  for (const p of patterns) {
    const m = markdown.match(p);
    const v = m?.[1]?.trim();
    if (v) return v;
  }
  return undefined;
}

function collect(markdown: string, patterns: RegExp[], limit = 30): string[] {
  const out: string[] = [];
  for (const p of patterns) {
    const ms = markdown.matchAll(p);
    for (const m of ms) {
      const v = String(m[1] ?? m[0] ?? '').trim();
      if (v) out.push(v);
    }
  }
  return uniq(out, limit);
}

function collectProcessLines(markdown: string): string[] {
  const rows = markdown
    .split('\n')
    .map(x => x.trim())
    .filter(Boolean);
  const hit = rows.filter(x => /工艺|加工|热处理|车削|铣削|磨削|钻孔|攻丝|焊接|淬火|回火|时效/i.test(x));
  return uniq(hit, 20);
}

export function mergeMultimodalMarkdownFromData(data: Record<string, unknown>): string {
  const descs = Array.isArray(data.multimodal_descriptions) ? data.multimodal_descriptions : [];
  const blocks = descs
    .map((one, idx) => {
      if (!one || typeof one !== 'object' || Array.isArray(one)) return '';
      const obj = one as Record<string, unknown>;
      const t = String(obj.type ?? obj.original_type ?? '').trim() || 'unknown';
      const text = String(obj.text_description ?? '').trim();
      if (!text) return '';
      return `### [${idx + 1}] ${t}\n\n${text}`;
    })
    .filter(Boolean);
  return blocks.join('\n\n---\n\n').trim();
}

export function parseMechanicalAnalysisResult(markdownInput: string): MechanicalAnalysisResult {
  const markdown = String(markdownInput || '').trim();
  if (!markdown) return { rawMarkdown: '' };

  const result: MechanicalAnalysisResult = {
    partType: pickFirst(markdown, [
      /零件(?:类型|名称)?[：:]\s*([^\n|]+)/i,
      /工件(?:类型|名称)?[：:]\s*([^\n|]+)/i,
      /part\s*type[：:]\s*([^\n|]+)/i
    ]),
    material: pickFirst(markdown, [
      /材料[：:]\s*([^\n|]+)/i,
      /材质[：:]\s*([^\n|]+)/i,
      /material[：:]\s*([^\n|]+)/i
    ]),
    heatTreatment: pickFirst(markdown, [
      /热处理[：:]\s*([^\n|]+)/i,
      /heat\s*treatment[：:]\s*([^\n|]+)/i
    ]),
    keyDimensions: collect(markdown, [
      /(\d+(?:\.\d+)?\s*(?:mm|cm|m|μm|um|°|HBW|HRC))/gi,
      /([ØΦ]\s*\d+(?:\.\d+)?(?:\s*mm)?)/gi,
      /((?:\d+(?:\.\d+)?\s*[x×*]\s*)+\d+(?:\.\d+)?\s*(?:mm|cm|m)?)/gi
    ]),
    tolerances: collect(markdown, [
      /([±]\s*\d+(?:\.\d+)?\s*(?:mm|μm|um)?)/gi,
      /(公差[：:]\s*[^\n，。;；]+)/gi,
      /(IT\d+(?:\s*~\s*IT\d+)?)/gi
    ]),
    datums: collect(markdown, [/((?:基准|Datum)[：:]\s*[A-Z0-9、,\s]+)/gi, /(\b[A-Z]\b(?=\s*基准))/gi]),
    roughness: collect(markdown, [/(Ra\s*\d+(?:\.\d+)?)/gi, /(Rz\s*\d+(?:\.\d+)?)/gi, /(粗糙度[：:]\s*[^\n，。;；]+)/gi]),
    features: collect(markdown, [/(特征[：:]\s*[^\n|]+)/gi, /(孔|槽|倒角|圆角|键槽|凸台|台阶|非圆|型腔|剖面)/gi], 40),
    threads: collect(markdown, [/(M\d+(?:\.\d+)?(?:\s*[x×]\s*\d+(?:\.\d+)?)?(?:[-\s]?[A-Z0-9]+)?)/gi, /(螺纹[：:]\s*[^\n，。;；]+)/gi]),
    sections: collect(markdown, [/(剖面[：:]\s*[^\n|]+)/gi, /(截面[：:]\s*[^\n|]+)/gi, /(section\s*[A-Z0-9-]+)/gi]),
    processes: collectProcessLines(markdown),
    feature_id: collect(markdown, [/(feature[_\s-]?id[：:]\s*([A-Za-z0-9_.-]+))/gi], 50),
    feature_type: collect(markdown, [/(feature[_\s-]?type[：:]\s*([A-Za-z0-9_\-\/ ]+))/gi], 50),
    relation: collect(markdown, [/(relation[：:]\s*([^\n|]+))/gi], 50),
    process_semantic: collect(markdown, [/(process[_\s-]?semantic[：:]\s*([^\n|]+))/gi], 50),
    rawMarkdown: markdown
  };

  return result;
}
