import { describe, it, expect } from 'vitest';
import { parseJsonLines } from './python-bridge';

describe('parseJsonLines — edge cases', () => {
  it('parses a complete line', () => {
    const [msgs, buf] = parseJsonLines('', '{"type":"result","data":{}}\n');
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('result');
    expect(buf).toBe('');
  });

  it('accumulates partial lines across two chunks', () => {
    const chunk1 = '{"type":"prog';
    const chunk2 = 'ress","phase":"dsm","percent":50,"message":"ok"}\n';
    const [msgs1, buf1] = parseJsonLines('', chunk1);
    expect(msgs1).toHaveLength(0);
    expect(buf1).toBe(chunk1);

    const [msgs2, buf2] = parseJsonLines(buf1, chunk2);
    expect(msgs2).toHaveLength(1);
    expect(msgs2[0].type).toBe('progress');
    expect(buf2).toBe('');
  });

  it('parses multiple messages in one chunk', () => {
    const chunk = '{"type":"progress","phase":"dsm","percent":10,"message":"a"}\n{"type":"result","data":{}}\n';
    const [msgs, buf] = parseJsonLines('', chunk);
    expect(msgs).toHaveLength(2);
    expect(msgs[0].type).toBe('progress');
    expect(msgs[1].type).toBe('result');
    expect(buf).toBe('');
  });

  it('strips UTF-8 BOM at the start', () => {
    const bomLine = '\uFEFF{"type":"result","data":{}}\n';
    const [msgs] = parseJsonLines('', bomLine);
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('result');
  });

  it('skips empty lines', () => {
    const chunk = '\n\n{"type":"result","data":{}}\n\n';
    const [msgs] = parseJsonLines('', chunk);
    expect(msgs).toHaveLength(1);
  });

  it('handles non-JSON on stdout gracefully — emits warning', () => {
    const [msgs] = parseJsonLines('', 'Some random text\n');
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('warning');
    expect((msgs[0] as unknown as { message: string }).message).toContain('Non-JSON on Python stdout');
  });

  it('keeps incomplete line in buffer', () => {
    const [msgs, buf] = parseJsonLines('', '{"type":"progress","percent":5');
    expect(msgs).toHaveLength(0);
    expect(buf).toBe('{"type":"progress","percent":5');
  });

  it('handles message with unknown type — emits warning', () => {
    const [msgs] = parseJsonLines('', '{"type":"unknown_type","data":1}\n');
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('warning');
  });

  it('handles message missing type field — emits warning', () => {
    const [msgs] = parseJsonLines('', '{"data":"no type here"}\n');
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('warning');
  });

  it('handles warning type', () => {
    const [msgs] = parseJsonLines('', '{"type":"warning","message":"watch out"}\n');
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe('warning');
  });
});
