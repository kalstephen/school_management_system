import { createTheme, type MantineColorsTuple } from "@mantine/core";

// SPEX brand book v1.0. "brand" is Secure · Electric Blue (#1E88E5) with its text shade
// #1565C0 used for filled buttons (white on blue is an approved pair); "navy" is SPEX Navy.
const brand: MantineColorsTuple = [
  "#e8f3fd", "#cfe6fb", "#a2cdf6", "#71b2f0", "#489ceb",
  "#2f8fe8", "#1e88e5", "#1565c0", "#0f4f9a", "#0b3b75",
];
const navy: MantineColorsTuple = [
  "#eef1f6", "#d8dfea", "#b0bdd2", "#8598b6", "#5f779c",
  "#45618b", "#2d4a73", "#1b3459", "#0b1f3a", "#07152a",
];

export const theme = createTheme({
  primaryColor: "brand",
  primaryShade: { light: 7, dark: 6 },
  colors: { brand, navy },
  defaultRadius: "md",
  black: "#16191F",
  fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  headings: {
    fontFamily: "Montserrat, Inter, system-ui, sans-serif",
    fontWeight: "700",
  },
  components: {
    Card: { defaultProps: { withBorder: true, radius: "md", padding: "lg" } },
    Paper: { defaultProps: { withBorder: true, radius: "md" } },
    Button: { defaultProps: { radius: "md" }, styles: { root: { fontFamily: "Montserrat, Inter, sans-serif", fontWeight: 600 } } },
    Table: { defaultProps: { highlightOnHover: true, verticalSpacing: "sm" } },
  },
});
