import { PropsWithChildren } from "react";
import { StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";

type SectionCardProps = PropsWithChildren<{
  eyebrow?: string;
  title: string;
  subtitle?: string;
}>;

export function SectionCard({ children, eyebrow, title, subtitle }: SectionCardProps) {
  return (
    <View style={styles.card}>
      {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      <View style={styles.body}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    gap: theme.spacing.sm,
    padding: theme.spacing.lg
  },
  eyebrow: {
    color: theme.colors.accent,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.2,
    textTransform: "uppercase"
  },
  title: {
    color: theme.colors.text,
    fontSize: 22,
    fontWeight: "800"
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: 14,
    lineHeight: 20
  },
  body: {
    gap: theme.spacing.md
  }
});
