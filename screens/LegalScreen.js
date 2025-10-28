import React from "react";
import { ScrollView, Text, StyleSheet, ImageBackground, View, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";

const BG = require("../assets/splash.jpg");

const POINTS = [
  "Our application is not directed to online gambling. It is only application for entertainment and fun between friends.. We do not support in any way gambling so understand that Gambling involves risk.",
  "Whilst we do are upmost to offer good analyze and information we cannot be held responsible for any choice you make outside our application that may incur as a result of  gambling.",
  "We do our best for all the info that we provide on this app, however from time to time mistakes will be made and we will not be held liable. Please check any stats or info is you are unsure how accurate they are.",
  "No guarantees are made with regards to results or financial gain. All forms of betting carry financial risk and it is down to individual decision.",
  "We can't be held responsible for any losses that may incur as a result of following the betting tips provided on this application because we share our opinion(analyze tips) for fun with friends.",
  "The material contained on this site is intended to inform and educate reader and in no way represents an inducement to gamble legaly or illegaly",
  "Past performance do not guarantee success in future.",
  "While we do our best to find the best for all our tips we can't ensure they are always accurate as betting odds fluctuate from one minute to the next.",
  "ALL TIPS are subject to change and were correct at the time of publishing.",
  "We are not be liable to you(whether under the law of contact, the law of torts or otherwise) in relation to the contents of, or use of, or otherwise in connection with this application."
];

export default function LegalScreen() {
  const router = useRouter();

  return (
    <ImageBackground source={BG} style={s.bg} imageStyle={s.bgImg}>
      <View style={s.scrim} />
      <ScrollView contentContainerStyle={s.wrap}>
        <View style={s.card}>
          <View style={s.glowEdge} />
          <View style={s.glowEdgeBottom} />
          <Text style={s.title}>Legal Disclaimer</Text>
          {POINTS.map((item, idx) => (
            <Text key={item} style={s.text}>
              {idx + 1}. {item}
            </Text>
          ))}
          <TouchableOpacity style={s.backBtn} onPress={() => router.push("/")}>
            <Text style={s.backTxt}>Back</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </ImageBackground>
  );
}

const s = StyleSheet.create({
  bg: { flex: 1, backgroundColor: "#050914" },
  bgImg: { resizeMode: "cover", opacity: 0.6 },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(4,10,26,0.55)" },
  wrap: { padding: 24 },
  card: {
    backgroundColor: "rgba(8,16,34,0.88)",
    borderRadius: 26,
    borderWidth: 1,
    borderColor: "rgba(88,160,255,0.5)",
    padding: 24,
    gap: 16,
    overflow: "hidden",
    shadowColor: "#58a0ff",
    shadowOpacity: 0.45,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 16 }
  },
  glowEdge: {
    position: "absolute",
    top: -80,
    right: -50,
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 2,
    borderColor: "rgba(91,224,255,0.35)",
    backgroundColor: "rgba(18,36,74,0.45)"
  },
  glowEdgeBottom: {
    position: "absolute",
    bottom: -70,
    left: -40,
    width: 200,
    height: 200,
    borderRadius: 100,
    borderWidth: 2,
    borderColor: "rgba(176,108,255,0.35)",
    backgroundColor: "rgba(40,16,72,0.4)"
  },
  title: { color: "#f5f9ff", fontSize: 26, fontWeight: "800", letterSpacing: 1.1 },
  text: { color: "#cbd9ff", fontSize: 15, lineHeight: 22 },
  backBtn: {
    alignSelf: "flex-start",
    marginTop: 8,
    paddingVertical: 10,
    paddingHorizontal: 22,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(94,230,255,0.6)",
    backgroundColor: "rgba(10,24,45,0.8)",
    shadowColor: "#5ee6ff",
    shadowOpacity: 0.5,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 }
  },
  backTxt: { color: "#e6f4ff", fontWeight: "700", letterSpacing: 0.6 }
});
