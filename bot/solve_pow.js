#!/usr/bin/env node
/**
 * Solve DeepSeek PoW challenge.
 * Reads { challenge, wasmUrl } JSON from stdin, outputs answer integer.
 */
async function main() {
    const input = await new Promise(resolve => {
        let d = "";
        process.stdin.on("data", c => d += c);
        process.stdin.on("end", () => resolve(d));
    });
    const { challenge, wasmUrl } = JSON.parse(input);

    const resp = await fetch(wasmUrl);
    const wasmBytes = await resp.arrayBuffer();
    const mod = await WebAssembly.instantiate(wasmBytes, { wbg: {} });
    const e = mod.instance.exports;
    const encoder = new TextEncoder();
    const prefix = challenge.salt + "_" + challenge.expire_at + "_";
    const cBytes = encoder.encode(challenge.challenge);
    const pBytes = encoder.encode(prefix);
    const cP = e.__wbindgen_export_0(cBytes.length, 1) >>> 0;
    const pP = e.__wbindgen_export_0(pBytes.length, 1) >>> 0;
    new Uint8Array(e.memory.buffer, cP, cBytes.length).set(cBytes);
    new Uint8Array(e.memory.buffer, pP, pBytes.length).set(pBytes);
    const sp = e.__wbindgen_add_to_stack_pointer(-16);
    e.wasm_solve(sp, cP, cBytes.length, pP, pBytes.length, challenge.difficulty);
    const dv = new DataView(e.memory.buffer);
    const code = dv.getInt32(sp, true);
    const ans = dv.getFloat64(sp + 8, true);
    e.__wbindgen_add_to_stack_pointer(16);
    if (code === 0 || !Number.isFinite(ans) || ans <= 0) {
        process.stderr.write("PoW failed\n");
        process.exit(1);
    }
    process.stdout.write(String(Math.floor(ans)));
}

main().catch(e => {
    process.stderr.write("PoW error: " + e.message + "\n");
    process.exit(1);
});
