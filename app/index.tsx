import React, { useCallback, useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, RefreshControl, ImageBackground, Linking } from "react-native";
import { useRouter } from "expo-router";
import TopMenu from "../components/TopMenu";

const FEED = "https://darkotosic.github.io/focus-bets-feed";
const BG = require("../assets/splash.jpg");

type Stat = { "2plus": boolean | null; "3plus": boolean | null; "4plus": boolean | null; date: string };

export default function Home() {
  const r = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [stat, setStat] = useState<Stat>({ "2plus": null, "3plus": null, "4plus": null, date: "" });

  const probe = async (slug: string) => {
    try {
      const res = await fetch(`${FEED}/${slug}.json`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const j = await res.json();
      return { ok: true, date: j?.date || "" };
    } catch {
      return { ok: false, date: "" };
    }
  };

  const load = useCallback(async () => {
    const [a, b, c] = await Promise.all([probe("2plus"), probe("3plus"), probe("4plus")]);
    setStat({ "2plus": a.ok, "3plus": b.ok, "4plus": c.ok, date: a.date || b.date || c.date || "" });
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const Dot = ({ ok }: { ok: boolean | null }) => (
    <View style={[s.dot, ok === true ? s.ok : ok === false ? s.bad : s.na]} />
  );

  return (
    <ImageBackground source={BG} style={s.bg} imageStyle={s.bgImg}>
      <View style={s.scrim} />
      <ScrollView
        style={s.wrap}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={s.container}>
          <View style={s.topMenuWrap}>
            <TopMenu />
          </View>

          <View style={s.bottomBlock}>
            <View style={s.row}>
              <TouchableOpacity
                style={s.btn}
                onPress={() => r.push({ pathname: "/ticket", params: { title: "2+ odds", url: `${FEED}/2plus.json` } })}
              >
                <Text style={s.bt}>2+ Odds</Text>
                <Dot ok={stat["2plus"]} />
              </TouchableOpacity>

              <TouchableOpacity
                style={s.btn}
                onPress={() => r.push({ pathname: "/ticket", params: { title: "3+ odds", url: `${FEED}/3plus.json` } })}
              >
                <Text style={s.bt}>3+ Odds</Text>
                <Dot ok={stat["3plus"]} />
              </TouchableOpacity>

              <TouchableOpacity
                style={s.btn}
                onPress={() => r.push({ pathname: "/ticket", params: { title: "4+ odds", url: `${FEED}/4plus.json` } })}
              >
                <Text style={s.bt}>4+ Odds</Text>
                <Dot ok={stat["4plus"]} />
              </TouchableOpacity>
            </View>

            <View style={[s.row, { marginTop: 16 }]}>
              <TouchableOpacity
                style={[s.btnWide, s.btnTelegram]}
                onPress={() => Linking.openURL("https://t.me/naksiranalysis")}
              >
                <Text style={s.bt}>Telegram</Text>
              </TouchableOpacity>
            </View>

            <View style={[s.row, { marginTop: 16 }]}>
              <TouchableOpacity style={s.btnWide} onPress={() => r.push("/strategy")}>
                <Text style={s.bt}>Stake Strategy Theory</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </ScrollView>
    </ImageBackground>
  );
}

const s = StyleSheet.create({
  bg: { flex: 1, backgroundColor: "#0b0f17" },
  bgImg: { resizeMode: "cover", opacity: 0.65 },
  wrap: { flex: 1 },
  content: { flexGrow: 1, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 32 },
  container: { flex: 1, justifyContent: "space-between" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(3,8,20,0.55)" },
  topMenuWrap: { paddingHorizontal: 4 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  btn: {
    flex: 1,
    marginHorizontal: 4,
    backgroundColor: "rgba(15,25,45,0.92)",
    borderColor: "rgba(80,160,255,0.45)",
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 18,
    alignItems: "center",
    shadowColor: "#3ca0ff",
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 10 }
  },
  btnWide: {
    flex: 1,
    backgroundColor: "rgba(15,25,45,0.92)",
    borderColor: "rgba(80,160,255,0.45)",
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 20,
    alignItems: "center",
    shadowColor: "#3ca0ff",
    shadowOpacity: 0.28,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 10 }
  },
  btnTelegram: {
    backgroundColor: "rgba(0,136,204,0.9)",
    borderColor: "rgba(0,136,204,0.8)",
    shadowColor: "#0088cc"
  },
  bt: { color: "#e6f1ff", fontWeight: "700", marginBottom: 6, fontSize: 15, letterSpacing: 0.5, textTransform: "uppercase" },
  dot: { width: 10, height: 10, borderRadius: 6, marginTop: 2 },
  ok: { backgroundColor: "#5ee6a8" },
  bad: { backgroundColor: "#ff8b8b" },
  na: { backgroundColor: "#6b7280" },
  bottomBlock: {
    justifyContent: "flex-end",
    gap: 12,
    paddingBottom: 12
  }
});
