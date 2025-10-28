import React from "react";
import { Drawer } from "expo-router/drawer";
import { DrawerContentScrollView, DrawerItem, DrawerContentComponentProps } from "@react-navigation/drawer";
import { StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import * as Linking from "expo-linking";

const FEED = "https://darkotosic.github.io/focus-bets-feed";

function CustomDrawerContent(props: DrawerContentComponentProps) {
  const router = useRouter();

  const close = () => props.navigation.closeDrawer();

  const items = [
    { label: "Home", action: () => router.push("/") },
    { label: "Privacy", action: () => Linking.openURL("https://naksirpredictions.top/privacy-policy") },
    { label: "Our Apps", action: () => Linking.openURL("https://play.google.com/store/apps/dev?id=6165954326742483653") },
    { label: "Telegram", action: () => Linking.openURL("https://t.me/naksiranalysis") },
    { label: "Naksir Website", action: () => Linking.openURL("https://naksirpredictions.top") },
    { label: "Legal", action: () => router.push("/legal") },
    { label: "Terms", action: () => router.push("/terms") },
    {
      label: "2+ Odds",
      action: () => router.push({ pathname: "/ticket", params: { title: "2+ odds", url: `${FEED}/2plus.json` } })
    },
    {
      label: "3+ Odds",
      action: () => router.push({ pathname: "/ticket", params: { title: "3+ odds", url: `${FEED}/3plus.json` } })
    },
    {
      label: "4+ Odds",
      action: () => router.push({ pathname: "/ticket", params: { title: "4+ odds", url: `${FEED}/4plus.json` } })
    },
    { label: "Stake Strategy", action: () => router.push("/strategy") }
  ];

  return (
    <DrawerContentScrollView {...props} contentContainerStyle={styles.drawerContent}>
      {items.map((item) => (
        <DrawerItem
          key={item.label}
          label={item.label}
          onPress={() => {
            item.action();
            close();
          }}
          labelStyle={styles.drawerLabel}
          style={styles.drawerItem}
        />
      ))}
    </DrawerContentScrollView>
  );
}

export default function Layout() {
  return (
    <Drawer
      screenOptions={{
        headerStyle: { backgroundColor: "#0b0f17" },
        headerTintColor: "#e6edf3",
        drawerStyle: { backgroundColor: "#05070d" },
        drawerActiveTintColor: "#111827",
        drawerInactiveTintColor: "#f8fbff",
        drawerActiveBackgroundColor: "#5ee6ff"
      }}
      drawerContent={(props) => <CustomDrawerContent {...props} />}
    >
      <Drawer.Screen name="index" options={{ title: "Focus" }} />
      <Drawer.Screen name="ticket" options={{ title: "Ticket", drawerItemStyle: { display: "none" } }} />
      <Drawer.Screen name="legal" options={{ title: "Legal" }} />
      <Drawer.Screen name="terms" options={{ title: "Terms" }} />
      <Drawer.Screen name="strategy" options={{ title: "Stake Strategy" }} />
    </Drawer>
  );
}

const styles = StyleSheet.create({
  drawerContent: {
    paddingTop: 24
  },
  drawerItem: {
    borderRadius: 12,
    marginHorizontal: 12,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: "#233144",
    backgroundColor: "rgba(94, 230, 255, 0.08)"
  },
  drawerLabel: {
    fontWeight: "700",
    letterSpacing: 0.5,
    color: "#f8fbff",
    textTransform: "uppercase"
  }
});
