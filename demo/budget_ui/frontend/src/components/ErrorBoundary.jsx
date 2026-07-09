import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { err: false }; }
  static getDerivedStateFromError() { return { err: true }; }
  componentDidCatch(err) { console.warn("[demo-ui] render error:", err); }
  render() {
    if (this.state.err) {
      return <div style={{ padding: 40, color: "#9FADC9", fontFamily: "monospace" }}>Building your pipeline...</div>;
    }
    return this.props.children;
  }
}
