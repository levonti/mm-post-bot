import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiForm, apiGet } from "../api/client";
import type { Locale } from "../api/types";
import { t } from "../i18n";

type Channel = {
  alias: string;
  channel_id: string;
  display_name?: string;
  team_name?: string;
};

type ChannelSearchResult = {
  id: string;
  name: string;
  display_name: string;
  team_name: string;
  label: string;
};

type TargetsPayload = {
  bots: Array<{ alias: string; bot_username: string }>;
  channels: Channel[];
  default: null | { bot_alias: string; channel_alias: string };
  stale_default: boolean;
};

export function TargetsPage({
  csrf,
  locale,
  targets
}: {
  csrf: string;
  locale: Locale;
  targets: TargetsPayload;
}) {
  const [channels, setChannels] = useState(targets.channels);
  const [defaultTarget, setDefaultTarget] = useState(targets.default);
  const [botAlias, setBotAlias] = useState(targets.default?.bot_alias || "");
  const [channelAlias, setChannelAlias] = useState(targets.default?.channel_alias || "");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ChannelSearchResult[]>([]);
  const [selected, setSelected] = useState<ChannelSearchResult | null>(null);
  const [newAlias, setNewAlias] = useState("");
  const [editingAlias, setEditingAlias] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setChannels(targets.channels);
  }, [targets.channels]);

  useEffect(() => {
    setDefaultTarget(targets.default);
    setBotAlias(targets.default?.bot_alias || targets.bots[0]?.alias || "");
    setChannelAlias(targets.default?.channel_alias || targets.channels[0]?.alias || "");
  }, [targets.bots, targets.channels, targets.default]);

  useEffect(() => {
    if (!searchOpen) return;
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      setResults([]);
      setStatus(t(locale, "web.targets.min_query"));
      return;
    }

    const timer = window.setTimeout(() => {
      setStatus(t(locale, "web.targets.searching"));
      setError(null);
      apiGet<{ results: ChannelSearchResult[] }>(
        `/api/web/targets/channels/search?q=${encodeURIComponent(normalizedQuery)}`
      )
        .then((payload) => {
          setResults(payload.results);
          setStatus(
            payload.results.length === 0 ? t(locale, "web.targets.no_results") : ""
          );
        })
        .catch((caught: unknown) => {
          setResults([]);
          setStatus("");
          setError(
            caught instanceof Error ? caught.message : t(locale, "web.targets.search_error")
          );
        });
    }, 250);

    return () => window.clearTimeout(timer);
  }, [locale, query, searchOpen]);

  const selectedAlias = useMemo(() => {
    if (selected === null) return "";
    return selected.name || selected.display_name || selected.id;
  }, [selected]);

  return (
    <section className="target-column">
      <div className="target-column-header">
        <h2>{t(locale, "web.targets.heading")}</h2>
        <button
          className="secondary-button"
          onClick={() => setSearchOpen((current) => !current)}
          type="button"
        >
          {t(locale, "web.targets.add_channel")}
        </button>
      </div>

      <section className="default-target-panel">
        <h3>{t(locale, "web.common.default_target")}</h3>
        <p className={targets.stale_default ? "target-summary warning" : "target-summary"}>
          {defaultTarget
            ? t(locale, "web.targets.current_default", {
                bot_alias: defaultTarget.bot_alias,
                channel_alias: defaultTarget.channel_alias
              })
            : targets.stale_default
              ? t(locale, "web.common.target_stale")
              : t(locale, "web.common.target_missing")}
        </p>
        <form className="default-target-form" onSubmit={setDefault}>
          <label htmlFor="default-bot-alias">{t(locale, "web.draft_detail.bot_alias")}</label>
          <select
            id="default-bot-alias"
            onChange={(event) => setBotAlias(event.target.value)}
            value={botAlias}
          >
            {targets.bots.map((bot) => (
              <option key={bot.alias} value={bot.alias}>
                {bot.alias}
              </option>
            ))}
          </select>
          <label htmlFor="default-channel-alias">
            {t(locale, "web.draft_detail.channel_alias")}
          </label>
          <select
            id="default-channel-alias"
            onChange={(event) => setChannelAlias(event.target.value)}
            value={channelAlias}
          >
            {channels.map((channel) => (
              <option key={channel.alias} value={channel.alias}>
                {channel.alias}
              </option>
            ))}
          </select>
          <div className="button-row">
            <button disabled={!botAlias || !channelAlias} type="submit">
              {t(locale, "web.targets.save_default")}
            </button>
            <button
              className="secondary-button"
              disabled={defaultTarget === null && !targets.stale_default}
              onClick={clearDefault}
              type="button"
            >
              {t(locale, "web.targets.clear_default")}
            </button>
          </div>
        </form>
      </section>

      {searchOpen ? (
        <section className="channel-search-panel">
          <label htmlFor="channel-search">{t(locale, "web.targets.search")}</label>
          <input
            id="channel-search"
            onChange={(event) => {
              setQuery(event.target.value);
              setSelected(null);
              setNewAlias("");
            }}
            type="search"
            value={query}
          />
          {status ? <p className="muted-meta">{status}</p> : null}
          {error ? (
            <p className="notice-banner notice-error" role="alert">
              {error}
            </p>
          ) : null}
          {results.length > 0 ? (
            <ul className="channel-result-list">
              {results.map((result) => (
                <li key={result.id}>
                  <button
                    className="channel-result-button"
                    onClick={() => {
                      setSelected(result);
                      setNewAlias(result.name || result.display_name || result.id);
                    }}
                    type="button"
                  >
                    {result.label || result.display_name || result.name || result.id}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {selected ? (
            <form className="channel-add-form" onSubmit={addSelectedChannel}>
              <p className="muted-meta">
                {t(locale, "web.targets.selected_channel")}:{" "}
                {selected.label || selected.display_name || selected.id}
              </p>
              <label htmlFor="new-channel-alias">{t(locale, "web.targets.alias")}</label>
              <input
                id="new-channel-alias"
                onChange={(event) => setNewAlias(event.target.value)}
                value={newAlias}
              />
              <div className="button-row">
                <button type="submit">{t(locale, "web.targets.save_channel")}</button>
                <button
                  className="secondary-button"
                  onClick={resetSearch}
                  type="button"
                >
                  {t(locale, "web.targets.cancel")}
                </button>
              </div>
            </form>
          ) : null}
        </section>
      ) : null}

      {channels.length === 0 ? (
        <p className="empty-state">{t(locale, "web.targets.empty_channels")}</p>
      ) : (
        <ul className="target-list">
          {channels.map((channel) => (
            <li className="channel-row" key={channel.alias}>
              <div className="channel-main">
                <strong>{channel.display_name || channel.alias}</strong>
                <span className="channel-id">{channel.channel_id}</span>
              </div>
              {editingAlias === channel.alias ? (
                <form className="channel-edit-form" onSubmit={renameChannel}>
                  <label className="sr-only" htmlFor={`channel-alias-${channel.alias}`}>
                    {t(locale, "web.targets.alias")}
                  </label>
                  <input
                    id={`channel-alias-${channel.alias}`}
                    onChange={(event) => setEditingValue(event.target.value)}
                    value={editingValue}
                  />
                  <button type="submit">{t(locale, "web.targets.save_alias")}</button>
                  <button
                    className="secondary-button"
                    onClick={() => setEditingAlias(null)}
                    type="button"
                  >
                    {t(locale, "web.targets.cancel")}
                  </button>
                </form>
              ) : (
                <>
                  <span className="channel-alias">{channel.alias}</span>
                  <button
                    type="button"
                    aria-label={`${t(locale, "web.targets.edit_alias")} ${channel.alias}`}
                    onClick={() => {
                      setEditingAlias(channel.alias);
                      setEditingValue(channel.alias);
                    }}
                  >
                    {t(locale, "web.targets.edit_alias")}
                  </button>
                  <button
                    type="button"
                    aria-label={`${t(locale, "web.targets.delete")} ${channel.alias}`}
                    onClick={() => deleteChannel(channel.alias)}
                  >
                    {t(locale, "web.targets.delete")}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <input name="csrf" type="hidden" value={csrf} />
    </section>
  );

  async function addSelectedChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected === null) return;
    const form = new FormData();
    form.set("csrf", csrf);
    form.set("channel_alias", (newAlias || selectedAlias).trim());
    form.set("channel_id", selected.id);
    form.set("channel_label", selected.label || selected.display_name || selected.id);
    const payload = await apiForm<{ alias: string; channel_id: string }>(
      "/api/web/targets/channels",
      form
    );
    setChannels((current) => [
      ...current,
      {
        alias: payload.alias,
        channel_id: payload.channel_id,
        display_name: selected.display_name,
        team_name: selected.team_name
      }
    ]);
    resetSearch();
  }

  async function renameChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingAlias === null) return;
    const form = new FormData();
    form.set("csrf", csrf);
    form.set("new_alias", editingValue);
    const payload = await apiForm<{ alias: string; channel_id: string }>(
      `/api/web/targets/channels/${encodeURIComponent(editingAlias)}/rename`,
      form
    );
    setChannels((current) =>
      current.map((channel) =>
        channel.alias === editingAlias ? { ...channel, alias: payload.alias } : channel
      )
    );
    setDefaultTarget((current) =>
      current?.channel_alias === editingAlias ? { ...current, channel_alias: payload.alias } : current
    );
    setChannelAlias((current) => (current === editingAlias ? payload.alias : current));
    setEditingAlias(null);
  }

  async function deleteChannel(alias: string) {
    if (!window.confirm(t(locale, "web.targets.delete_confirm", { alias }))) {
      return;
    }
    const form = new FormData();
    form.set("csrf", csrf);
    await apiForm(`/api/web/targets/channels/${encodeURIComponent(alias)}/delete`, form);
    setChannels((current) => current.filter((channel) => channel.alias !== alias));
    setDefaultTarget((current) => (current?.channel_alias === alias ? null : current));
    setChannelAlias((current) => (current === alias ? "" : current));
  }

  async function setDefault(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData();
    form.set("csrf", csrf);
    form.set("bot_alias", botAlias);
    form.set("channel_alias", channelAlias);
    await apiForm("/api/web/targets/default", form);
    setDefaultTarget({ bot_alias: botAlias, channel_alias: channelAlias });
  }

  async function clearDefault() {
    const form = new FormData();
    form.set("csrf", csrf);
    await apiForm("/api/web/targets/default/clear", form);
    setDefaultTarget(null);
  }

  function resetSearch() {
    setSearchOpen(false);
    setQuery("");
    setResults([]);
    setSelected(null);
    setNewAlias("");
    setStatus("");
    setError(null);
  }
}
