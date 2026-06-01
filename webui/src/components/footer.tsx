export function FooterHelp() {
  return (
    <footer className="px-6 py-6 pb-8 text-center text-xs text-muted-2 tracking-wide">
      快捷键： <Kbd>R</Kbd> 刷新 · <Kbd>G</Kbd> 网格 · <Kbd>T</Kbd> 时间流 · <Kbd>1</Kbd> 国内
      · <Kbd>2</Kbd> 国际
    </footer>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block min-w-[18px] px-1.5 py-px mx-0.5 border border-border-strong rounded-xs font-mono text-xs leading-none text-fg bg-panel">
      {children}
    </kbd>
  );
}
