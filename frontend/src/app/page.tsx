import { AppShell } from "@/components/AppShell";
import { SessionProvider } from "@/store/SessionProvider";

export default function Home() {
  return (
    <SessionProvider>
      <AppShell />
    </SessionProvider>
  );
}
