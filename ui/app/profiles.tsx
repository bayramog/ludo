// Profiles (#78): several people on one machine, each with their own RomM
// account, saves and history. The list and the Steam links live in the
// backend (romm_sync_engine.profiles); switching restarts the backend under
// the chosen profile and reloads the page.
//
// Desktop only: on the Deck there is one profile, get_profiles answers
// {supported: false} and none of this renders.
import { useEffect, useRef, useState, type Ref } from "react";
import { Focusable, GamepadButton, ModalRoot, host, showModal } from "@ludo/host";
import { FaCheck, FaPen, FaPlus, FaSteam, FaTrash, FaUnlink, FaUsers } from "react-icons/fa";
import { V2 } from "./theme";
import { V2Focus, V2_FOCUS_STYLE } from "./focus";
import { MODAL_SCRIM_INSET, UserMenuRow, V2TextField, useArmedPress } from "./kit";
import { _forceGamepadFocus } from "./shell";
import { holdToasts, toaster } from "./toast";
import { dropProfileStorage, storageProfile, swapProfileStorage } from "./storage";
import {
  createProfile, discardProfile, getProfiles, linkProfileSteam, removeProfile, renameProfile, switchProfile, unlinkProfileSteam,
} from "./rpc";

export type Profile = {
  id: string; name: string; custom_name: boolean; username: string; role: string;
  avatar: string | null; steam: string[]; signed_in: boolean; current: boolean; removable: boolean; local_saves?: number;
};
export type SteamAccount = { id: string; name: string; linked_to: string | null };
export type ProfileList = {
  supported: boolean; current?: string; ask?: boolean;
  steam?: { id: string; name: string } | null; profiles?: Profile[];
  steam_accounts?: SteamAccount[];
};

// Initials stand in for a missing avatar: one of a few gradients, stable per
// profile so a face doesn't change colour between visits.
const GRADIENTS = [
  'linear-gradient(135deg,#f472b6,#a855f7)', 'linear-gradient(135deg,#38bdf8,#22c55e)',
  'linear-gradient(135deg,#fb923c,#ef4444)', 'linear-gradient(135deg,#facc15,#f97316)',
  'linear-gradient(135deg,#818cf8,#06b6d4)',
];
function gradientFor(id: string) {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return GRADIENTS[h % GRADIENTS.length];
}

export function ProfileAvatar({ profile, size }: { profile: Profile; size: number }) {
  return (
    <div style={{
      width: `${size}px`, height: `${size}px`, borderRadius: '50%', flexShrink: 0, overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: profile.avatar ? V2.bgElevated : gradientFor(profile.id),
      color: '#fff', fontWeight: 700, fontSize: `${Math.round(size * 0.42)}px`,
    }}>
      {profile.avatar
        ? <img src={profile.avatar} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        : (profile.name || '?').slice(0, 1).toUpperCase()}
    </div>
  );
}

function subtitle(p: Profile) {
  if (!p.signed_in) return 'Not signed in yet';
  // An unrenamed profile is named after its RomM user: only a renamed one
  // needs to say which account it is.
  return p.username && p.username.toLowerCase() !== p.name.toLowerCase() ? p.username : '';
}


// Restart the backend into another profile. The page reloads behind the boot
// cover (index.html) until initProfiles has the new profile's screen up;
// `picker` reopens the profile picker there (Back from a new profile's welcome).
function restartInto(id: string, picker = false) {
  sessionStorage.setItem('romm:switching', '1');
  if (picker) sessionStorage.setItem('romm:reopen-picker', '1');
  // Fade the whole window to the boot cover's colour now, so the restart reads
  // as one fade out and in: without it the screen behind the picker showed
  // again for a moment, then cut to black.
  const veil = document.createElement('div');
  veil.style.cssText = 'position:fixed;inset:0;background:#07070f;z-index:2147483647;opacity:0;transition:opacity .16s ease';
  document.body.appendChild(veil);
  requestAnimationFrame(() => { veil.style.opacity = '1'; });
  swapProfileStorage(id);
  host.app.reloadBackend();
}

function liftBootCover() {
  sessionStorage.removeItem('romm:switching');
  const el = document.getElementById('boot-cover');
  if (!el) return;
  // Two frames for the first screen to paint, then fade out.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 250);
  }));
}

// Open a profile: the backend records the choice (and links the Steam account
// that launched us), then the shell restarts it under that profile.
// True only when that restart is under way: picking the profile already in use
// ('ok') must still close the picker, or its faded scrim stays over the app
// and swallows every click.
export async function openProfile(id: string): Promise<boolean> {
  const r = await switchProfile(id);
  if (r?.status === 'reload') {
    restartInto(id);
    return true;
  }
  if (r?.status === 'error') toaster.toast({ urgent: true, title: 'Could not switch profile', body: r.message || '' });
  return false;
}

// Back out of a just-added profile from its welcome screen: the profile it
// was added from opens again and this unfinished one is deleted.
export async function discardNewProfile(): Promise<boolean> {
  const r = await discardProfile().catch((e: any) => ({ message: String(e?.message || e) }));
  if (r?.status === 'reload' && r.id) {
    restartInto(r.id, true);
    return true;
  }
  toaster.toast({ urgent: true, title: 'Could not go back', body: r?.message || '' });
  return false;
}

// The account menu's "Switch profile" row, with the other profiles' faces.
// The name of the profile in use, for the top bar's pill: on a shared machine
// the pill says who is playing, not which RomM account they sign in with.
// '' until known, or on shells without profiles (the caller falls back to the
// RomM username). Refreshed when a rename lands.
const PROFILES_CHANGED = 'ludo:profiles-changed';
export function useCurrentProfileName(): string {
  const [name, setName] = useState('');
  useEffect(() => {
    let alive = true;
    const load = () => getProfiles()
      .then((l: ProfileList) => {
        const cur = l?.supported ? l.profiles?.find((p) => p.current) : undefined;
        if (alive) setName(cur?.name || '');
      })
      .catch(() => {});
    load();
    window.addEventListener(PROFILES_CHANGED, load);
    return () => { alive = false; window.removeEventListener(PROFILES_CHANGED, load); };
  }, []);
  return name;
}

export function SwitchProfileRow({ onOpen }: { onOpen: () => void }) {
  const [list, setList] = useState<ProfileList | null>(null);
  useEffect(() => { getProfiles().then(setList).catch(() => setList(null)); }, []);
  if (!list?.supported) return null;
  const others = (list.profiles ?? []).filter((p) => !p.current).slice(0, 3);
  return (
    <UserMenuRow icon={<FaUsers size={15} />} label="Switch profile" onSelect={onOpen}
      trailing={others.length ? (
        <div style={{ display: 'flex', marginLeft: 'auto' }}>
          {others.map((p, i) => (
            <div key={p.id} style={{ marginLeft: i ? '-6px' : 0, border: '2px solid #15151f', borderRadius: '50%' }}>
              <ProfileAvatar profile={p} size={18} />
            </div>
          ))}
        </div>
      ) : undefined} />
  );
}

// Hover moves focus, it doesn't light a card by itself: with both, the focused
// card and the hovered one were lit at once. One highlight, one A target.
function ProfileCard({ profile, onPick, onManage, cardRef, index, chosen, managing }:
  { profile: Profile; onPick: () => void; onManage: () => void; cardRef?: Ref<HTMLDivElement>;
    index: number; chosen: boolean; managing: boolean }) {
  const [focused, setHot] = useState(false);
  // Manage takes focus into its panel; the card it was opened on stays lit
  // behind it, so the highlight doesn't drop out and come back on return.
  const hot = focused || managing;
  return (
    <Focusable noFocusRing ref={cardRef} onActivate={onPick} onClick={onPick}
      className={`pf-card${chosen ? ' pf-chosen' : ''}`} data-pid={profile.id}
      onSecondaryButton={onManage} onSecondaryActionDescription="Manage"
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}
      onMouseEnter={(e: any) => _forceGamepadFocus(e.currentTarget)}
      style={{
        width: '176px', padding: '18px 14px 16px', borderRadius: '16px', boxSizing: 'border-box',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', textAlign: 'center',
        cursor: 'pointer',
        // Stays dark when focused: a see-through light fill turned grey over the
        // bright covers blurred behind the picker. Focus is the border and lift.
        background: hot ? 'linear-gradient(180deg,rgba(34,34,48,0.92),rgba(18,18,28,0.95))'
          : 'linear-gradient(180deg,rgba(20,20,30,0.72),rgba(10,10,18,0.8))',
        // Focus is the app's tile treatment (brand ring + glow + scale), the
        // same as covers and platform tiles.
        // Border longhands, not the shorthand: with the shorthand plus the focus
        // borderColor, React dropped the colour on blur and it went white.
        borderWidth: '1px', borderStyle: 'solid', borderColor: V2.border, transform: 'none', boxShadow: 'none',
        ...V2Focus.tile(hot),
        transition: 'transform .15s cubic-bezier(0.22,1,0.36,1), background .15s ease, border-color .15s ease, box-shadow .15s ease',
        animationDelay: `${60 + index * 45}ms`,
      }}>
      <div style={{ position: 'relative' }}>
        <ProfileAvatar profile={profile} size={84} />
        {profile.current && (
          // An SVG, not a bordered div: the focus scale re-rasterised the CSS
          // circle at a fractional size and its edge visibly changed shape.
          <svg width="24" height="24" viewBox="0 0 24 24" style={{ position: 'absolute', right: '-2px', bottom: '-2px', overflow: 'visible' }}>
            <circle cx="12" cy="12" r="10.5" fill="#22c55e" stroke={hot ? '#20202d' : '#12121b'} strokeWidth="3"
              style={{ transition: 'stroke .14s ease' }} />
            <path d="M7.6 12.2l2.9 2.9 5.9-5.9" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <div style={{ fontSize: '16px', fontWeight: 700, color: V2.fg, marginTop: '4px', maxWidth: '100%',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.name}</div>
      {subtitle(profile) && <div style={{ fontSize: '11.5px', color: V2.fgMuted, lineHeight: 1.2 }}>{subtitle(profile)}</div>}
      {/* Its own flex item, so the card's gap spaces it like the rest. */}
      {profile.steam.length > 0 && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', maxWidth: '100%', boxSizing: 'border-box',
          padding: '3px 9px', lineHeight: 1.2, borderRadius: '999px', background: 'rgba(255,255,255,0.08)',
          color: V2.fg, fontSize: '11.5px' }}>
          <FaSteam size={11} style={{ flexShrink: 0 }} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.steam.join(', ')}</span>
        </div>
      )}
      {profile.current
        ? <div style={{ fontSize: '10.5px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: '#4ade80' }}>Playing now</div>
        : <div style={{ height: '15px' }} />}
    </Focusable>
  );
}

function AddProfileCard({ onAdd, index }: { onAdd: () => void; index: number }) {
  const [hot, setHot] = useState(false);
  return (
    <Focusable noFocusRing onActivate={onAdd} onClick={onAdd} className="pf-card"
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}
      onMouseEnter={(e: any) => _forceGamepadFocus(e.currentTarget)}
      style={{
        width: '176px', padding: '18px 14px 16px', borderRadius: '16px', boxSizing: 'border-box',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', textAlign: 'center',
        cursor: 'pointer',
        // Dashed at rest, solid brand when focused so no dashes show under the ring.
        borderWidth: '1.5px', borderStyle: hot ? 'solid' : 'dashed', borderColor: hot ? V2.brand : 'rgba(255,255,255,0.22)',
        background: hot ? 'rgba(24,24,34,0.85)' : 'rgba(5,5,10,0.55)',
        transform: 'none', boxShadow: 'none',
        ...V2Focus.tile(hot),
        transition: 'transform .15s cubic-bezier(0.22,1,0.36,1), background .15s ease, border-color .15s ease, box-shadow .15s ease',
        animationDelay: `${60 + index * 45}ms`,
      }}>
      <div style={{ width: '84px', height: '84px', borderRadius: '50%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.7)' }}>
        <FaPlus size={28} />
      </div>
      <div style={{ fontSize: '16px', fontWeight: 700, color: V2.fg, marginTop: '4px' }}>Add profile</div>
      <div style={{ height: '15px' }} />
    </Focusable>
  );
}

// Picker motion, in the app's overlay idiom (rdIn/umIn): the title and cards
// rise in left to right, the pick pulses, the exit fades. The blurred scrim
// itself appears at once: fading it in flashed the sharp library for a few
// frames right after the account menu (also blurred) closed.
// The rise uses translate/scale, not transform, so it composes with the
// focused card's transform scale instead of snapping to it at the end.
const PICKER_MOTION = `
  @keyframes pfRise { from { opacity: 0; translate: 0 6px; scale: 0.985; } to { opacity: 1; translate: none; scale: none; } }
  @keyframes pfPulse { 0% { transform: scale(1.04); } 45% { transform: scale(1.09); box-shadow: 0 0 0 4px rgba(139,116,232,.35), 0 0 28px rgba(139,116,232,.6), 0 16px 40px rgba(0,0,0,.55); } 100% { transform: scale(1.04); } }
  .pf-scrim { transition: opacity .16s ease-in, background-color .45s ease, backdrop-filter .45s ease; }
  @keyframes pfFade { from { opacity: 0; } }
  .pf-embedded { animation: pfFade .18s .1s ease-out backwards; }
  .pf-scrim.pf-leaving { opacity: 0; pointer-events: none; }
  .pf-rise { animation: pfRise .26s cubic-bezier(.2,.8,.2,1) backwards; }
  .pf-card { animation: pfRise .3s cubic-bezier(.2,.8,.2,1) backwards; }
  .pf-card.pf-chosen { animation: pfPulse .22s ease-out; }
  @media (prefers-reduced-motion: reduce) {
    .pf-scrim, .pf-embedded, .pf-rise, .pf-card, .pf-card.pf-chosen { animation: none !important; transition: none !important; }
  }
`;
const REDUCED_MOTION = () => !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

// "Who's playing?": every profile as a card. A to open, the Details button to
// manage one. Shown from the account menu, and by itself at launch when a
// Steam account with no profile yet opens the app on a machine with several.
// embedded: rendered inside the account menu's own modal, on its blurred scrim,
// in place of the menu panel. onLeaving lets that host fade its scrim with us.
export function ProfilePickerModal({ closeModal, embedded, onLeaving, solid }:
  { closeModal?: () => void; embedded?: boolean; onLeaving?: () => void; solid?: boolean }) {
  const [list, setList] = useState<ProfileList | null>(null);
  const [busy, setBusy] = useState(false);
  // Opened at launch, the page behind is still filling its rows: hold a solid
  // backdrop until it has settled (no new elements, images loaded), then
  // fade over to the usual blurred view of it.
  const [opaque, setOpaque] = useState(!!solid);
  useEffect(() => {
    if (!solid) return;
    let last = -1, still = 0;
    const started = Date.now();
    const t = setInterval(() => {
      const n = document.getElementsByTagName('*').length;
      const loading = [...document.images].some((i) => !i.complete);
      still = n === last && !loading ? still + 1 : 0;
      last = n;
      if (still >= 3 || Date.now() - started > 4000) { clearInterval(t); setOpaque(false); }
    }, 100);
    return () => clearInterval(t);
  }, []);
  // Animated exit: fade the picker out, then unmount it. The chosen card
  // pulses first so a switch reads as a step, not a glitch.
  const [leaving, setLeaving] = useState(false);
  useEffect(() => holdToasts(), []);
  const [chosen, setChosen] = useState<string | null>(null);
  const close = () => {
    if (leaving) return;
    setLeaving(true);
    onLeaving?.();
    setTimeout(() => closeModal?.(), REDUCED_MOTION() ? 0 : 160);
  };
  const rowRef = useRef<HTMLDivElement>(null);
  const currentRef = useRef<HTMLDivElement>(null);
  const load = () => getProfiles().then(setList).catch(() => setList({ supported: false }));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!list?.profiles) return;
    // Onto the profile in use, not the row: focusing the row lit no card, so
    // a picker opened with the mouse showed no Select/Manage hints.
    const t = setTimeout(() => {
      const target = currentRef.current
        || rowRef.current?.querySelector<HTMLElement>('[tabindex]')
        || rowRef.current;
      if (target) _forceGamepadFocus(target);
    }, 60);
    return () => clearTimeout(t);
  }, [!!list?.profiles]);

  const pick = async (p: Profile) => {
    if (busy) return;
    setBusy(true);
    setChosen(p.id);
    try {
      if (!REDUCED_MOTION()) await new Promise((res) => setTimeout(res, 220));
      setLeaving(true);
      const reloading = await openProfile(p.id);
      if (!reloading) closeModal?.();
    } catch (e) {
      setLeaving(false); setChosen(null);
      throw e;
    } finally { setBusy(false); }
  };
  const add = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await createProfile('');
      if (r?.status === 'reload' && r.id) {
        // Fade out as a pick does; the restart behind it takes a moment.
        setLeaving(true);
        restartInto(r.id);
      } else {
        toaster.toast({ urgent: true, title: 'Could not add a profile', body: r?.message || '' });
      }
    } finally { setBusy(false); }
  };
  // Back from Manage, focus returns to the card it was opened on (or the one
  // in use, if that profile was just removed): by itself it only came back for
  // the pad, so a mouse user returned to a picker with nothing selected.
  const [managing, setManaging] = useState<string | null>(null);
  const refocus = (id: string) => setTimeout(() => {
    setManaging(null);
    const card = rowRef.current?.querySelector<HTMLElement>(`[data-pid="${id}"]`) || currentRef.current;
    if (card) _forceGamepadFocus(card);
  }, 80);
  const manage = (p: Profile) => {
    setManaging(p.id);
    showModal(<ProfileManageModal profile={p} accounts={list?.steam_accounts ?? []} profiles={profiles} onChanged={load} onPick={() => pick(p)} onClosed={() => refocus(p.id)} />);
  };

  // Opened at launch (Back from a new profile), the page behind readies its own
  // focus once its games load and took it off the card: hold it in here.
  useEffect(() => {
    const keep = (e: FocusEvent) => {
      const scrim = rowRef.current?.closest('.pf-scrim');
      if (!scrim || leaving || managing || scrim.contains(e.target as Node)) return;
      const t = currentRef.current || rowRef.current?.querySelector<HTMLElement>('[tabindex]');
      if (t) _forceGamepadFocus(t);
    };
    document.addEventListener('focusin', keep);
    return () => document.removeEventListener('focusin', keep);
  }, [leaving, managing]);

  const profiles = list?.profiles ?? [];
  const body = (
    <Focusable noFocusRing className={`romm-ui pf-scrim${embedded ? ' pf-embedded' : ''}${opaque && !embedded ? ' pf-solid' : ''}${leaving ? ' pf-leaving' : ''}`}
        onCancelButton={close}
        onButtonDown={(e: any) => { if (e?.detail?.button === GamepadButton.CANCEL) close(); }}
        style={{
          position: 'fixed', inset: MODAL_SCRIM_INSET, zIndex: 9999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '28px',
          // Embedded: the account menu's scrim already blurs the page; a second
          // blur here would re-raster when the menu's went away, and some GPUs
          // skip the blur for a couple of frames then (sharp library flash).
          // Solid when opened at launch: the page behind is still filling its
          // rows then, and that showed through the blur. It's ready by the
          // time a profile is picked and this fades away.
          ...(embedded ? {} : {
            background: 'rgba(7,7,15,0.55)',
            WebkitBackdropFilter: 'blur(10px)', backdropFilter: 'blur(10px)',
          }),
          fontFamily: V2.font, color: V2.fg,
        }}>
        <style>{`
          ${V2_FOCUS_STYLE}
          ${PICKER_MOTION}
          .romm-modal-collapse, .romm-modal-collapse > div {
            background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important;
          }
          /* Beats the rule above, which also caught the scrim's inline colour. */
          .romm-modal-collapse .pf-scrim.pf-solid { background: ${V2.bg} !important; }
        `}</style>
        <div onClick={close} style={{ position: 'absolute', inset: 0 }} />
        <div className="pf-rise" style={{ position: 'relative', textAlign: 'center' }}>
          <div style={{ fontSize: '26px', fontWeight: 800 }}>Who's playing?</div>
        </div>
        <Focusable noFocusRing autoFocus ref={rowRef} flow-children="horizontal"
          style={{ position: 'relative', display: 'flex', gap: '18px', alignItems: 'stretch', flexWrap: 'wrap',
            justifyContent: 'center', maxWidth: '90vw', opacity: busy && !chosen ? 0.6 : 1 }}>
          {profiles.map((p, i) => <ProfileCard key={p.id} profile={p} cardRef={p.current ? currentRef : undefined}
            index={i} chosen={chosen === p.id} managing={managing === p.id}
            onPick={() => pick(p)} onManage={() => manage(p)} />)}
          {list?.supported && <AddProfileCard onAdd={add} index={profiles.length} />}
        </Focusable>
        {list?.steam && (
          <div className="pf-rise" style={{ position: 'relative', fontSize: '12px', color: V2.fgMuted, animationDelay: '120ms' }}>
            Signed in to Steam as <b style={{ color: V2.fg }}>{list.steam.name}</b>: the profile you pick opens here next time.
          </div>
        )}
      </Focusable>
    );
  return embedded ? body : (
    <ModalRoot bHideCloseIcon onCancel={close} onEscKeypress={close}
      className="romm-modal-collapse" modalClassName="romm-modal-collapse">{body}</ModalRoot>
  );
}

// The Details-button menu on a profile card.
function ProfileManageModal({ profile, accounts, profiles, onChanged, onPick, onClosed, closeModal }:
  { profile: Profile; accounts: SteamAccount[]; profiles: Profile[]; onChanged: () => void; onPick: () => void; onClosed?: () => void; closeModal?: () => void }) {
  // Closed for real, not React's dev-mode check that unmounts and remounts
  // every new component once: that one fired onClosed while the panel was
  // still up, and the card behind it lost its highlight.
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      setTimeout(() => { if (!mounted.current) onClosed?.(); }, 0);
    };
  }, []);
  const panelRef = useRef<HTMLDivElement>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(profile.custom_name ? profile.name : '');
  useEffect(() => { const t = setTimeout(() => { if (panelRef.current) _forceGamepadFocus(panelRef.current); }, 60); return () => clearTimeout(t); }, [renaming]);
  const done = () => { onChanged(); closeModal?.(); };
  const removeWith = async (saves: boolean) => {
    const r = await removeProfile(profile.id, saves);
    if (r?.status === 'ok') dropProfileStorage(profile.id);
    else toaster.toast({ urgent: true, title: 'Could not remove profile', body: r?.message || '' });
    done();
  };
  const remove = useArmedPress(() => removeWith(false));
  const removeAll = useArmedPress(() => removeWith(true));
  const saveCount = profile.local_saves ?? 0;
  const saveName = async () => {
    const r = await renameProfile(profile.id, name);
    if (r?.status !== 'ok') toaster.toast({ urgent: true, title: 'Could not rename profile', body: r?.message || '' });
    else window.dispatchEvent(new Event(PROFILES_CHANGED));
    done();
  };
  const unlink = async () => { await unlinkProfileSteam(profile.id); done(); };
  const link = async (a: SteamAccount) => {
    const r = await linkProfileSteam(profile.id, a.id);
    if (r?.status !== 'ok') toaster.toast({ urgent: true, title: 'Could not link Steam user', body: r?.message || '' });
    done();
  };
  // Every Steam account signed in on this machine that isn't on this profile
  // yet. Works from a desktop launch too: linking only needs the account id.
  const linkable = accounts.filter((a) => a.linked_to !== profile.id);
  const ownerName = (id: string | null) => profiles.find((p) => p.id === id)?.name;

  return (
    <ModalRoot bHideCloseIcon onCancel={closeModal} onEscKeypress={closeModal}
      className="romm-modal-collapse" modalClassName="romm-modal-collapse">
      <Focusable noFocusRing className="romm-ui"
        onCancelButton={() => closeModal?.()}
        onButtonDown={(e: any) => { if (e?.detail?.button === GamepadButton.CANCEL) closeModal?.(); }}
        style={{
          position: 'fixed', inset: MODAL_SCRIM_INSET, zIndex: 10000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(7,7,15,0.5)', WebkitBackdropFilter: 'blur(6px)', backdropFilter: 'blur(6px)',
        }}>
        <div onClick={() => closeModal?.()} style={{ position: 'absolute', inset: 0 }} />
        <Focusable noFocusRing ref={panelRef} flow-children="vertical" style={{
          position: 'relative', width: '300px', padding: '8px', boxSizing: 'border-box',
          fontFamily: V2.font, color: V2.fg, display: 'flex', flexDirection: 'column',
          background: 'linear-gradient(180deg, rgba(20,20,30,0.85) 0%, rgba(10,10,18,0.9) 100%)',
          border: '1px solid rgba(255,255,255,0.12)', borderRadius: V2.radiusCard,
          boxShadow: '0 16px 48px rgba(0,0,0,0.55)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 8px 12px' }}>
            <ProfileAvatar profile={profile} size={34} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '13px', fontWeight: 700 }}>{profile.name}</div>
              <div style={{ fontSize: '10.5px', fontWeight: 600, color: V2.fgMuted, marginTop: '2px' }}>
                {profile.signed_in ? `${profile.username} on RomM` : 'Not signed in yet'}
              </div>
            </div>
          </div>
          <div style={{ height: '1px', background: V2.border, margin: '0 4px 4px' }} />
          {renaming ? (
            <div style={{ padding: '6px 6px 4px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <V2TextField label="Profile name" value={name} onChange={setName} maxLength={40}
                placeholder={profile.username || 'Name'} onEnter={saveName} />
              <UserMenuRow icon={<FaCheck size={14} />} label="Save name" onSelect={saveName} />
            </div>
          ) : (
            <>
              {!profile.current && (
                <UserMenuRow icon={<FaCheck size={14} />} label={`Switch to ${profile.name}`}
                  onSelect={() => { closeModal?.(); onPick(); }} />
              )}
              <UserMenuRow icon={<FaPen size={14} />} label="Rename" onSelect={() => setRenaming(true)} />
              {linkable.map((a) => (
                <UserMenuRow key={a.id} icon={<FaSteam size={14} />} label={`Link Steam user ${a.name}`} onSelect={() => link(a)}
                  trailing={a.linked_to && ownerName(a.linked_to) ? (
                    <span style={{ marginLeft: 'auto', fontSize: '11px', color: V2.fgMuted, whiteSpace: 'nowrap' }}>
                      from {ownerName(a.linked_to)}
                    </span>
                  ) : undefined} />
              ))}
              {profile.steam.length > 0 && (
                <UserMenuRow icon={<FaUnlink size={14} />} label={`Unlink Steam user ${profile.steam.join(', ')}`} onSelect={unlink} />
              )}
              {!accounts.length && (
                <div style={{ fontSize: '11px', color: V2.fgMuted, padding: '4px 12px 6px', lineHeight: 1.4 }}>
                  No Steam account is signed in on this machine to link.
                </div>
              )}
              {profile.removable && (
                <>
                  <div style={{ height: '1px', background: V2.border, margin: '4px' }} />
                  <UserMenuRow icon={<FaTrash size={14} />} danger armed={remove.armed}
                    label={remove.armed ? 'Press again to remove' : 'Remove profile'} onSelect={remove.press} />
                  <div style={{ fontSize: '11px', color: V2.fgMuted, padding: '2px 12px 8px 39px', lineHeight: 1.4 }}>
                    {saveCount ? 'Its saves on RomM and on this device are kept.' : 'Its saves on RomM are kept.'}
                  </div>
                  {saveCount > 0 && (
                    <>
                      <UserMenuRow icon={<FaTrash size={14} />} danger armed={removeAll.armed}
                        label={removeAll.armed ? 'Press again to delete' : 'Remove profile and its saves'} onSelect={removeAll.press} />
                      <div style={{ fontSize: '11px', color: V2.fgMuted, padding: '2px 12px 8px 39px', lineHeight: 1.4 }}>
                        Also deletes its {saveCount} save and state {saveCount === 1 ? 'file' : 'files'} on this device.
                        Copies on RomM are kept; anything not uploaded yet is lost.
                      </div>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </Focusable>
      </Focusable>
    </ModalRoot>
  );
}

// At launch. The backend may have opened a different profile than the one
// this window's stored caches belong to (another Steam account started us):
// swap them and reload once. Then, a Steam account with no profile yet on a
// machine with more than one is asked who is playing.
export async function initProfiles() {
  const reopen = sessionStorage.getItem('romm:reopen-picker');
  try {
    const list: ProfileList = await getProfiles();
    if (list?.supported && list.current && storageProfile() !== list.current) {
      swapProfileStorage(list.current);
      location.reload();
      return;  // the cover stays up over this reload too
    }
    sessionStorage.removeItem('romm:reopen-picker');
    // Back from a new profile lands in the picker, on the profile it came from.
    if (list?.supported && (list.ask || reopen)) {
      showModal(<ProfilePickerModal solid />);
      // Lift the cover once the picker has finished coming in (the modal's
      // fade and the cards' rise): lifted together, the half-faded picker let
      // the page behind show through for a moment.
      setTimeout(liftBootCover, REDUCED_MOTION() ? 0 : 450);
      return;
    }
  } catch { /* single-profile shells have nothing to ask */ }
  liftBootCover();
}
