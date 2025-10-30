import React from "react";
import { View, TouchableOpacity, Text, StyleSheet, Linking } from "react-native";
import { useRouter } from "expo-router";

const LINKS = [
  { label: "Privacy", type: "external", target: "https://naksirpredictions.top/privacy-policy" },
  { label: "Legal", type: "internal", target: "/legal" },
  { label: "Terms", type: "internal", target: "/terms" }
];

export default function TopMenu() {
  const router = useRouter();

  return (
    <View style={s.wrap}>
      {LINKS.map((item) => (
        <TouchableOpacity
          key={item.label}
          style={s.btn}
          onPress={() => {
            if (item.type === "external") {
              Linking.openURL(item.target);
            } else {
              router.push(item.target);
            }
          }}
          accessibilityRole="button"
        >
          <Text style={s.txt}>{item.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingTop: 6,
    alignSelf: "stretch"
  },
  btn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(94,230,255,0.45)",
    backgroundColor: "rgba(10,18,36,0.75)",
    shadowColor: "#58c4ff",
    shadowOpacity: 0.35,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 }
  },
  txt: { color: "#d7ecff", fontWeight: "700", letterSpacing: 0.6, textTransform: "uppercase", fontSize: 12 }
});
