import React from "react";
import { ScrollView, Text, StyleSheet, ImageBackground, View, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";

const BG = require("../assets/splash.jpg");

const BODY = `These terms and conditions outline the rules and regulations for the use of the application, created by Soccer Analysis NAKSIR. This application is only informative tool and must be used just for fun. We post various sports prediction that represent our opinion regarding the eventual outcome of those games. This is not a betting application, it is not related to betting or gambling in any way. We do not encourage or support betting and gambling.By continuing to use app you accept to our terms and conditions, you fully understand that this is only informative service and you accept that we will not be in any what responsible for your personal actions. Everyone who uses the app is 100% responsible for his actions and for obeying the applicable laws in his country. Act responsibly! 18+ Only. Not designed for children! If you want to review the Terms and Conditions later you can do that at any time in the app menu. If you have any questions or concerns regarding these T&C or Agreement please contact us 365soccertips@gmail.com.`;

export default function TermsScreen() {
  const router = useRouter();

  return (
    <ImageBackground source={BG} style={s.bg} imageStyle={s.bgImg}>
      <View style={s.scrim} />
      <ScrollView contentContainerStyle={s.wrap}>
        <View style={s.card}>
          <View style={s.glowEdge} />
          <View style={s.glowEdgeBottom} />
          <Text style={s.title}>Terms of Use</Text>
          <Text style={s.text}>{BODY}</Text>
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
    borderColor: "rgba(94,180,255,0.55)",
    padding: 24,
    gap: 18,
    overflow: "hidden",
    shadowColor: "#58a0ff",
    shadowOpacity: 0.45,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 16 }
  },
  glowEdge: {
    position: "absolute",
    top: -70,
    right: -60,
    width: 230,
    height: 230,
    borderRadius: 115,
    borderWidth: 2,
    borderColor: "rgba(91,224,255,0.35)",
    backgroundColor: "rgba(20,38,76,0.45)"
  },
  glowEdgeBottom: {
    position: "absolute",
    bottom: -60,
    left: -60,
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 2,
    borderColor: "rgba(176,108,255,0.35)",
    backgroundColor: "rgba(42,18,74,0.42)"
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
