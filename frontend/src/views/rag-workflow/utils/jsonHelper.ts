import Json5 from 'json5';

/** 安全解析 JSON5，失败返回 ``null`` */
export function safeParseJson5(text: string): unknown | null {
  const t = text.trim();
  if (!t) return null;
  try {
    return Json5.parse(t);
  } catch {
    return null;
  }
}

export function stringifyPretty(value: unknown): string {
  try {
    return JSON.stringify(value ?? null, null, 2);
  } catch {
    return String(value);
  }
}

/** 文本能否解析为 JSON5 值 */
export function isValidJson5(text: string): boolean {
  const t = text.trim();
  if (!t) return true;
  try {
    Json5.parse(t);
    return true;
  } catch {
    return false;
  }
}
