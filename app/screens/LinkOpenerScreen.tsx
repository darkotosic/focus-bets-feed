import React, { useCallback, useEffect } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';

export type LinkOpenerScreenProps = {
  url: string;
  label: string;
};

export const LinkOpenerScreen: React.FC<LinkOpenerScreenProps> = ({ url, label }) => {
  const open = useCallback(async () => {
    const supported = await Linking.canOpenURL(url);
    if (supported) {
      await Linking.openURL(url);
    }
  }, [url]);

  useEffect(() => {
    open();
  }, [open]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{label}</Text>
      <Text style={styles.subtitle}>Opening link in your default browser…</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0b1120',
    padding: 24,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#f9fafb',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#cbd5f5',
    textAlign: 'center',
  },
});

export default LinkOpenerScreen;
