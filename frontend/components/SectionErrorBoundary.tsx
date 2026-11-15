"use client";

import { Component, type ReactNode } from "react";

class SectionErrorBoundary extends Component<{ children: ReactNode; label: string }, { failed: boolean }> {
  constructor(props: { children: ReactNode; label: string }) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) {
      return (
        <div className="card p-3.5 text-[12px] text-zinc-500">
          Couldn&apos;t render this section ({this.props.label}) — the rest of the report is unaffected.
        </div>
      );
    }
    return this.props.children;
  }
}

export default SectionErrorBoundary;
