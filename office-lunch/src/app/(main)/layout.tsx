import { QueryPanel } from "@/components/query-panel";
import { Sidebar } from "@/components/sidebar";
import { UserProvider } from "@/components/user-context";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserProvider>
      <div className="lg:flex">
        <Sidebar />
        <main className="mx-auto w-full min-w-0 max-w-6xl px-4 pb-24 pt-6 sm:px-8 lg:pt-10"><p className="mb-4 text-xs text-muted">Dữ liệu food: mã item và yes/no gốc. Tên món, giá, hồ sơ và ngữ cảnh là dữ liệu demo bổ sung.</p>{children}</main>
      </div>
      <QueryPanel />
    </UserProvider>
  );
}
