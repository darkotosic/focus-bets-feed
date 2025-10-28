import React from "react";
import { ScrollView, Text, StyleSheet, ImageBackground } from "react-native";

export default function StrategyScreen() {
  return (
    <ImageBackground
      source={require("../assets/backgrounds/strategy-bg.png")}
      style={s.bg}
      imageStyle={s.bgImg}
      resizeMode="cover"
    >
      <ScrollView style={s.wrap} contentContainerStyle={{ padding: 12 }}>
        <Text style={s.h1}>Stake Strategy Theory</Text>
        <Text style={s.p}>
          Educational content. No betting encouragement. Use units, not currency. For analysis and learning only.
        </Text>

        <Text style={s.h2}>1) Conservative plan</Text>
        <Text style={s.p}>
          Daily exposure ≈ 2% of bankroll as units. Example: 100 units bankroll → 2 units total per day.
          Distribution across tickets: 2+ = 1.0u, 3+ = 0.7u, 4+ = 0.3u. Goal: variance control.
        </Text>

        <Text style={s.h2}>2) Balanced plan</Text>
        <Text style={s.p}>
          Daily risk up to 3%. Example: 100u → 3u per day. Split: 2+ = 1.2u, 3+ = 1.0u, 4+ = 0.8u.
          Stop after planned exposure. Track results weekly.
        </Text>

        <Text style={s.h2}>3) Fractional Kelly (aggressive)</Text>
        <Text style={s.p}>
          Kelly units = f * ((p * o - (1 - p)) / (o - 1)), where o=decimal odds, p=estimated edge 0–1, f∈(0,0.5].
          Use fractional f=0.25 by default. Cap stake ≤ 2% per ticket. If formula gives ≤0 → skip.
        </Text>

        <Text style={s.h2}>Risk rules</Text>
        <Text style={s.li}>• Units only. No cash amounts.</Text>
        <Text style={s.li}>• Fixed daily cap. No chasing.</Text>
        <Text style={s.li}>• Logs: date, ticket, units, outcome.</Text>
        <Text style={s.li}>• Content is informational and for fans of statistics.</Text>
      </ScrollView>
    </ImageBackground>
  );
}

const s = StyleSheet.create({
  bg: { flex: 1 },
  bgImg: { width: "100%", height: "100%" },
  wrap: { flex: 1, backgroundColor: "rgba(11, 15, 23, 0.88)" },
  h1: { color: "#e6edf3", fontSize: 20, fontWeight: "800", marginBottom: 6 },
  h2: { color: "#cfe2ff", fontSize: 16, fontWeight: "700", marginTop: 14, marginBottom: 4 },
  p: { color: "#9fb0c9", lineHeight: 20 },
  li: { color: "#9fb0c9", marginTop: 6 }
});
