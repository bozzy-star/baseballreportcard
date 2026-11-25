// ベースボール通信簿 定時起動係（Cloudflare Worker）
// GitHub の定時実行は10時間以上遅れることがあるため、
// Cloudflare の Cron Trigger から決まった時刻に daily.yml を起動する。
// GitHub 側の定時実行は予備として残す（処理は重複しても何も起きない）。
//
// 必要な設定：Secret「GITHUB_TOKEN」（Actions: Read and write だけを許可した細粒度トークン）

const REPO = "bozzy-star/baseballreportcard";
const WORKFLOW = "daily.yml";

// UTC の「時:分」→ 対象と再確認フラグ（JST は +9 時間）
const SLOTS = {
  "5:33":  { slot: "hs",   late: "" },     // 14:33 高校の部
  "8:7":   { slot: "hs",   late: "true" }, // 17:07 高校の部 再確認
  "7:7":   { slot: "univ", late: "" },     // 16:07 大学の部（昼の試合の日）
  "9:37":  { slot: "univ", late: "true" }, // 18:37 大学の部 再確認
  "11:7":  { slot: "univ", late: "" },     // 20:07 大学の部
  "13:7":  { slot: "univ", late: "true" }, // 22:07 大学の部 再確認
};

async function dispatch(env, inputs) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "brc-dispatcher",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  // 成功時は 204（本文なし）
  const text = res.status === 204 ? "" : await res.text();
  return { status: res.status, text };
}

export default {
  async scheduled(event, env, ctx) {
    const t = new Date(event.scheduledTime);
    const key = `${t.getUTCHours()}:${t.getUTCMinutes()}`;
    const inputs = SLOTS[key] || { slot: "all", late: "" };
    const r = await dispatch(env, inputs);
    console.log(`dispatch ${key} ${JSON.stringify(inputs)} -> ${r.status} ${r.text}`);
    if (r.status !== 204) throw new Error(`dispatch failed: ${r.status}`);
  },

  // 動作確認用：ブラウザで開くと稼働中かどうかだけ返す（起動はしない）
  async fetch(request, env) {
    return new Response(
      `brc-dispatcher ok / token ${env.GITHUB_TOKEN ? "set" : "missing"}\n`,
      { headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  },
};
