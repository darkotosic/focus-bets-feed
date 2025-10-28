import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

type TextContentScreenProps = {
  title: string;
  body: string[];
};

export const TextContentScreen: React.FC<TextContentScreenProps> = ({ title, body }) => (
  <ScrollView contentContainerStyle={styles.container}>
    <View style={styles.inner}>
      <Text style={styles.title}>{title}</Text>
      {body.map((paragraph, idx) => (
        <Text key={idx} style={styles.paragraph}>
          {paragraph}
        </Text>
      ))}
    </View>
  </ScrollView>
);

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'flex-start',
    backgroundColor: '#0b1120',
    padding: 24,
  },
  inner: {
    gap: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#e0e7ff',
  },
  paragraph: {
    fontSize: 16,
    lineHeight: 24,
    color: '#cbd5f5',
  },
});

export default TextContentScreen;
