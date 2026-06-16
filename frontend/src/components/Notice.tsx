export function Notice({ kind, message }: { kind: "error" | "success"; message: string }) {
  return (
    <section className={`notice-banner notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {message}
    </section>
  );
}
