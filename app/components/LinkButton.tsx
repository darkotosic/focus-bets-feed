import React from 'react';
import { Pressable, StyleSheet, Text, ViewStyle } from 'react-native';

type LinkButtonProps = {
  label: string;
  onPress: () => void;
  style?: ViewStyle | ViewStyle[];
  variant?: 'primary' | 'secondary';
};

export const LinkButton: React.FC<LinkButtonProps> = ({ label, onPress, style, variant = 'primary' }) => {
  const buttonStyle = [styles.button, variant === 'secondary' ? styles.secondary : styles.primary];
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [buttonStyle, pressed && styles.pressed, style]}>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  button: {
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 6,
  },
  primary: {
    backgroundColor: '#1f2937',
  },
  secondary: {
    backgroundColor: '#0f172a',
  },
  pressed: {
    opacity: 0.75,
  },
  label: {
    color: '#f9fafb',
    fontSize: 18,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
});

export default LinkButton;
