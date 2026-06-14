type Channel = {
  alias: string;
  channel_id: string;
  display_name?: string;
  team_name?: string;
};

type TargetsPayload = {
  bots: Array<{ alias: string; bot_username: string }>;
  channels: Channel[];
  default: null | { bot_alias: string; channel_alias: string };
  stale_default: boolean;
};

export function TargetsPage({ csrf, targets }: { csrf: string; targets: TargetsPayload }) {
  return (
    <section className="target-column">
      <div className="target-column-header">
        <h2>Channels</h2>
        <button className="secondary-button" type="button">
          Add channel
        </button>
      </div>
      <ul className="target-list">
        {targets.channels.map((channel) => (
          <li className="channel-row" key={channel.alias}>
            <div className="channel-main">
              <strong>{channel.display_name || channel.alias}</strong>
              <span className="channel-id">{channel.channel_id}</span>
            </div>
            <span className="channel-alias">{channel.alias}</span>
            <button type="button" aria-label={`Edit alias ${channel.alias}`}>
              Edit alias
            </button>
            <button
              type="button"
              aria-label={`Delete ${channel.alias}`}
              onClick={() => window.confirm(`Delete channel ${channel.alias}?`)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <input name="csrf" type="hidden" value={csrf} />
    </section>
  );
}
