import type { CSSProperties } from "react";

export const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.75rem",
  marginBottom: "0.7rem",
};

export const legendStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  justifyContent: "flex-end",
  gap: "0.4rem 0.65rem",
  color: "#68736d",
  fontSize: "0.65rem",
};

export const canvasStyle: CSSProperties = {
  width: "100%",
  height: "26rem",
  minHeight: 320,
  overflow: "hidden",
  border: "1px solid #d9dfda",
  borderRadius: 14,
  background: "#f7f9f6",
};

export const detailsStyle: CSSProperties = {
  marginTop: "0.75rem",
  border: "1px solid #d9dfda",
  borderRadius: 14,
  background: "#ffffff",
  padding: "0.85rem",
};

export const detailsHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "start",
  justifyContent: "space-between",
  gap: "0.75rem",
};

export const codeStyle: CSSProperties = {
  maxWidth: "52%",
  overflow: "hidden",
  borderRadius: 6,
  background: "#eef1ed",
  padding: "0.2rem 0.35rem",
  color: "#34423b",
  fontSize: "0.62rem",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const factsStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  margin: "0.75rem 0 0",
};

export const sectionTitleStyle: CSSProperties = {
  margin: "0 0 0.4rem",
  color: "#68736d",
  fontSize: "0.64rem",
  letterSpacing: "0.07em",
  textTransform: "uppercase",
};

export const pillListStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.35rem",
};

export const pillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.3rem",
  maxWidth: "100%",
  overflow: "hidden",
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: "#d9dfda",
  borderRadius: 999,
  background: "#f7f9f6",
  padding: "0.22rem 0.45rem",
  color: "#34423b",
  fontSize: "0.62rem",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const activePillStyle: CSSProperties = {
  borderColor: "#82b6a6",
  background: "#e4f2ed",
  color: "#0f4f44",
};

export const legalPillStyle: CSSProperties = {
  borderColor: "#e5a28f",
  background: "#fcebe6",
  color: "#753423",
};

export const transitionListStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  margin: 0,
  padding: 0,
  listStyle: "none",
  fontSize: "0.67rem",
};
