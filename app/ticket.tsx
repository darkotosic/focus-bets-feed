import { useLocalSearchParams, useNavigation } from "expo-router";
import TicketScreen from "../screens/TicketScreen";
import { useEffect } from "react";

export default function TicketPage() {
  const { title, url } = useLocalSearchParams<{title:string; url:string;}>();
  const nav = useNavigation();
  useEffect(()=>{ nav.setOptions({ title: title || "Ticket" }); },[nav, title]);
  return <TicketScreen route={{ params:{ title, url }}} navigation={nav as any} />;
}
