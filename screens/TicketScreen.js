import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  ImageBackground,
  TouchableOpacity
} from "react-native";

const emoji = { win: "✅", lose: "❌", pending: "⏳", none: "" };

export default function TicketScreen({ route, navigation }) {
  const { title, url } = route.params;
  const [data, setData] = useState(null);        // tiket
  const [evalData, setEvalData] = useState(null); // evaluacija
  const [err, setErr] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const evalUrlFrom = (u) => u.replace(/\/([^/]+)\.json$/, "/eval_$1.json");

  const load = useCallback(async () => {
    try {
      setErr("");
      const [r1, r2] = await Promise.all([
        fetch(url, { cache: "no-store" }),
        fetch(evalUrlFrom(url), { cache: "no-store" }).catch(() => null)
      ]);
      if (!r1?.ok) throw new Error(`HTTP ${r1?.status || "?"} feed`);
      const j1 = await r1.json();

      let j2 = null;
      if (r2 && r2.ok) j2 = await r2.json(); // eval može još da ne postoji tokom dana

      setData(j1);
      setEvalData(j2);
      // naslov + ukupni status
      const head = j2?.ticket_result ? ` (${j2.ticket_result.toUpperCase()})` : "";
      navigation.setOptions({ title: `${title}${head}` });
    } catch (e) {
      setErr(String(e.message || e));
    }
  }, [url, title]);

  useEffect(() => { navigation.setOptions({ title }); load(); }, [title]);

  const onRefresh = useCallback(async () => { setRefreshing(true); await load(); setRefreshing(false); }, [load]);

  // pomoćna mapa: fixture_id -> result object
  const resultById = (() => {
    const map = new Map();
    if (evalData?.legs) {
      for (const r of evalData.legs) map.set(Number(r.fixture_id), r);
    }
    return map;
  })();

  const ticketEmoji = evalData?.ticket_result ? emoji[evalData.ticket_result] : "";

  const formatOdds = (val) => {
    const num = Number(val);
    return Number.isFinite(num) ? num.toFixed(2) : "—";
  };

  const ticketData = data ? data.ticket || data : null;
  const legs = ticketData?.legs && Array.isArray(ticketData.legs) ? ticketData.legs : [];
  const totalOdds = ticketData?.total_odds ?? data?.total_odds ?? null;
  const ticketDate = (() => {
    if (typeof data?.date === "string" && data.date.trim()) return data.date.trim();
    if (typeof ticketData?.date === "string" && ticketData.date.trim()) return ticketData.date.trim();
    return "";
  })();

  return (
    <ImageBackground
      source={require("../assets/backgrounds/ticket-bg.png")}
      style={s.bg}
      imageStyle={s.bgImg}
      resizeMode="cover"
    >
      <ScrollView style={s.wrap} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.navigate("index") }>
          <Text style={s.backTxt}>← Back to Home</Text>
        </TouchableOpacity>
        {!data && !err && <ActivityIndicator style={{ marginTop: 30 }} />}
        {err ? <Text style={s.err}>{err}</Text> : null}

        {ticketData && (
          <View>
            <Text style={s.h1}>
              {ticketDate} • total {formatOdds(totalOdds)} {ticketEmoji}
            </Text>

            {legs.map((L, i) => {
              const rid = Number(L.fixture_id ?? L.fid ?? 0);
              const r = resultById.get(rid);
              const state = r?.result || "none";
              const mark = emoji[state] || "";
              const score = r?.score_ft ? ` • FT ${r.score_ft}` : "";

              const league = L.league || "";
              const teams = L.teams || [L.home ?? L.home_name, L.away ?? L.away_name].filter(Boolean).join(" vs ");
              const kickoff = L.kickoff_local || L.time || "";
              const market = L.market || "";
              const pick = L.pick ?? L.pick_name ?? "";
              const odds = formatOdds(L.odds ?? L.odd);

              return (
                <View key={i} style={s.card}>
                  <Text style={s.lg}>{league}</Text>
                  <Text style={s.tm}>{teams || ""}</Text>
                  <Text style={s.kf}>{kickoff}</Text>
                  <Text style={s.mk}>Pick: {market} → {pick}</Text>
                  <Text style={s.od}>Odds: {odds}</Text>
                  <Text style={[s.res, state==="win"?s.ok: state==="lose"?s.bad:s.pending]}>
                    {mark} {r ? r.result.toUpperCase() : "—"}{score}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </ImageBackground>
  );
}

const s = StyleSheet.create({
  bg: { flex: 1 },
  bgImg: { width: "100%", height: "100%" },
  wrap: { flex: 1, backgroundColor: "rgba(11, 15, 23, 0.88)", padding: 12 },
  backBtn: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(94, 230, 255, 0.15)",
    borderColor: "#5ee6ff",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginBottom: 12
  },
  backTxt: { color: "#f8fbff", fontWeight: "700", letterSpacing: 0.5 },
  h1: { color: "#e6edf3", fontSize: 16, fontWeight: "700", marginBottom: 10 },
  card: { borderWidth: 1, borderColor: "#243041", backgroundColor: "#0f141f", borderRadius: 14, padding: 12, marginBottom: 10 },
  lg: { color: "#8fb3ff", fontWeight: "600" },
  tm: { color: "#e6edf3", marginTop: 4, fontSize: 16 },
  kf: { color: "#9fb0c9", marginTop: 2 },
  mk: { color: "#d1eaff", marginTop: 6 },
  od: { color: "#b6f0c2", marginTop: 2, fontWeight: "700" },
  res: { marginTop: 8, fontWeight: "700" },
  ok: { color: "#8ef0a5" },
  bad: { color: "#ff9aa2" },
  pending: { color: "#ffde7a" },
  err: { color: "#ffb4b4", marginTop: 20 }
});
