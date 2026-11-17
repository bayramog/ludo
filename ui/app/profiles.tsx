// Profiles (#78): several people on one machine, each with their own RomM
// account, saves and history. The list and the Steam links live in the
// backend (romm_sync_engine.profiles); switching restarts the backend under
// the chosen profile and reloads the page.
//
// Desktop only: on the Deck there is one profile, get_profiles answers
// {supported: false} and none of this renders.
import { useEffect, useRef, useState, type Ref } from "react";
import { Focusable, GamepadButton, ModalRoot, host, showModal } from "@ludo/host";
import { FaCheck, FaLink, FaPen, FaPlus, FaTrash, FaUsers } from "react-icons/fa";
import { V2 } from "./theme";
import { V2_FOCUS_STYLE } from "./focus";
import { MODAL_SCRIM_INSET, UserMenuRow, V2TextField, useArmedPress } from "./kit";
import { _forceGamepadFocus } from "./shell";
import { toaster } from "./toast";
import { dropProfileStorage, storageProfile, swapProfileStorage } from "./storage";
import {
  createProfile, getProfiles, removeProfile, renameProfile, switchProfile, unlinkProfileSteam,
} from "./rpc";

export type Profile = {
  id: string; name: string; custom_name: boolean; username: string; role: string;
  avatar: string | null; steam: string[]; signed_in: boolean; current: boolean; removable: boolean;
};
export type ProfileList = {
  supported: boolean; current?: string; ask?: boolean;
  steam?: { id: string; name: string } | null; profiles?: Profile[];
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
  return p.role ? `${p.username} · ${p.role.charAt(0).toUpperCase()}${p.role.slice(1)}` : p.username;
}

function steamLine(p: Profile) {
  if (!p.steam.length) return 'Not linked to a Steam user';
  return `Opens for Steam user ${p.steam.join(', ')}`;
}

// Open a profile: the backend records the choice (and links the Steam account
// that launched us), then the shell restarts it under that profile.
export async function openProfile(id: string): Promise<boolean> {
  const r = await switchProfile(id);
  if (r?.status === 'reload') {
    toaster.toast({ title: 'Switching profile…', body: '' });
    swapProfileStorage(id);
    host.app.reloadBackend();
    return true;
  }
  if (r?.status === 'error') toaster.toast({ title: 'Could not switch profile', body: r.message || '' });
  return r?.status === 'ok';
}

// The account menu's "Switch profile" row, with the other profiles' faces.
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

function ProfileCard({ profile, onPick, onManage, cardRef }:
  { profile: Profile; onPick: () => void; onManage: () => void; cardRef?: Ref<HTMLDivElement> }) {
  const [hot, setHot] = useState(false);
  return (
    <Focusable noFocusRing ref={cardRef} onActivate={onPick} onClick={onPick}
      onSecondaryButton={onManage} onSecondaryActionDescription="Manage"
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}
      onMouseEnter={() => setHot(true)} onMouseLeave={() => setHot(false)}
      style={{
        width: '176px', padding: '22px 14px 16px', borderRadius: '16px', boxSizing: 'border-box',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', textAlign: 'center',
        cursor: 'pointer',
        // Stays dark when focused: a see-through light fill turned grey over the
        // bright covers blurred behind the picker. Focus is the border and lift.
        background: hot ? 'linear-gradient(180deg,rgba(34,34,48,0.92),rgba(18,18,28,0.95))'
          : 'linear-gradient(180deg,rgba(20,20,30,0.72),rgba(10,10,18,0.8))',
        border: `1px solid ${hot ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.12)'}`,
        transform: hot ? 'scale(1.04)' : 'none',
        boxShadow: hot ? '0 12px 32px rgba(0,0,0,.5)' : 'none',
        transition: 'transform .14s ease, background .14s ease, border-color .14s ease',
      }}>
      <div style={{ position: 'relative' }}>
        <ProfileAvatar profile={profile} size={84} />
        {profile.current && (
          <div style={{
            position: 'absolute', right: '-2px', bottom: '-2px', width: '24px', height: '24px', borderRadius: '50%',
            background: '#22c55e', border: '3px solid #12121b', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><FaCheck size={10} color="#fff" /></div>
        )}
      </div>
      <div style={{ fontSize: '16px', fontWeight: 700, color: V2.fg, marginTop: '4px', maxWidth: '100%',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.name}</div>
      <div style={{ fontSize: '11.5px', color: V2.fgMuted, lineHeight: 1.45 }}>
        {subtitle(profile)}<br />{steamLine(profile)}
      </div>
      {profile.current
        ? <div style={{ fontSize: '10.5px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: '#4ade80', marginTop: '2px' }}>Playing now</div>
        : <div style={{ height: '15px' }} />}
    </Focusable>
  );
}

function AddProfileCard({ onAdd }: { onAdd: () => void }) {
  const [hot, setHot] = useState(false);
  return (
    <Focusable noFocusRing onActivate={onAdd} onClick={onAdd}
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}
      onMouseEnter={() => setHot(true)} onMouseLeave={() => setHot(false)}
      style={{
        width: '176px', padding: '22px 14px 16px', borderRadius: '16px', boxSizing: 'border-box',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', textAlign: 'center',
        cursor: 'pointer',
        border: `1.5px dashed ${hot ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.22)'}`,
        background: hot ? 'rgba(24,24,34,0.85)' : 'transparent',
        transform: hot ? 'scale(1.04)' : 'none',
        transition: 'transform .14s ease, background .14s ease, border-color .14s ease',
      }}>
      <div style={{ width: '84px', height: '84px', borderRadius: '50%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.7)' }}>
        <FaPlus size={28} />
      </div>
      <div style={{ fontSize: '16px', fontWeight: 700, color: V2.fg, marginTop: '4px' }}>Add profile</div>
      <div style={{ fontSize: '11.5px', color: V2.fgMuted, lineHeight: 1.45 }}>Sign in with another<br />RomM account</div>
      <div style={{ height: '15px' }} />
    </Focusable>
  );
}

// "Who's playing?": every profile as a card. A to open, the Details button to
// manage one. Shown from the account menu, and by itself at launch when a
// Steam account with no profile yet opens the app on a machine with several.
export function ProfilePickerModal({ closeModal }: { closeModal?: () => void }) {
  const [list, setList] = useState<ProfileList | null>(null);
  const [busy, setBusy] = useState(false);
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
    try {
      const reloading = await openProfile(p.id);
      if (!reloading) closeModal?.();
    } finally { setBusy(false); }
  };
  const add = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await createProfile('');
      if (r?.status === 'reload' && r.id) {
        toaster.toast({ title: 'New profile', body: 'Sign in with its RomM account.' });
        swapProfileStorage(r.id);
        host.app.reloadBackend();
      } else {
        toaster.toast({ title: 'Could not add a profile', body: r?.message || '' });
      }
    } finally { setBusy(false); }
  };
  const manage = (p: Profile) => showModal(<ProfileManageModal profile={p} onChanged={load} onPick={() => pick(p)} />);

  const profiles = list?.profiles ?? [];
  return (
    <ModalRoot bHideCloseIcon onCancel={closeModal} onEscKeypress={closeModal}
      className="romm-modal-collapse" modalClassName="romm-modal-collapse">
      <Focusable noFocusRing className="romm-ui"
        onCancelButton={() => closeModal?.()}
        onButtonDown={(e: any) => { if (e?.detail?.button === GamepadButton.CANCEL) closeModal?.(); }}
        style={{
          position: 'fixed', inset: MODAL_SCRIM_INSET, zIndex: 9999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '28px',
          background: 'rgba(7,7,15,0.55)',
          WebkitBackdropFilter: 'blur(10px)', backdropFilter: 'blur(10px)',
          fontFamily: V2.font, color: V2.fg,
        }}>
        <style>{`
          ${V2_FOCUS_STYLE}
          .romm-modal-collapse, .romm-modal-collapse > div {
            background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important;
          }
        `}</style>
        <div onClick={() => closeModal?.()} style={{ position: 'absolute', inset: 0 }} />
        <div style={{ position: 'relative', textAlign: 'center' }}>
          <div style={{ fontSize: '26px', fontWeight: 800 }}>Who's playing?</div>
          <div style={{ fontSize: '13px', color: V2.fgMuted, marginTop: '8px' }}>
            Each profile has its own RomM account, saves and play history. Games stay shared.
          </div>
        </div>
        <Focusable noFocusRing autoFocus ref={rowRef} flow-children="horizontal"
          style={{ position: 'relative', display: 'flex', gap: '18px', alignItems: 'stretch', flexWrap: 'wrap',
            justifyContent: 'center', maxWidth: '90vw', opacity: busy ? 0.6 : 1 }}>
          {profiles.map((p) => <ProfileCard key={p.id} profile={p} cardRef={p.current ? currentRef : undefined}
            onPick={() => pick(p)} onManage={() => manage(p)} />)}
          {list?.supported && <AddProfileCard onAdd={add} />}
        </Focusable>
        {list?.steam && (
          <div style={{ position: 'relative', fontSize: '12px', color: V2.fgMuted }}>
            Signed in to Steam as <b style={{ color: V2.fg }}>{list.steam.name}</b>: the profile you pick opens here next time.
          </div>
        )}
      </Focusable>
    </ModalRoot>
  );
}

// The Details-button menu on a profile card.
function ProfileManageModal({ profile, onChanged, onPick, closeModal }:
  { profile: Profile; onChanged: () => void; onPick: () => void; closeModal?: () => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(profile.custom_name ? profile.name : '');
  useEffect(() => { const t = setTimeout(() => { if (panelRef.current) _forceGamepadFocus(panelRef.current); }, 60); return () => clearTimeout(t); }, [renaming]);
  const done = () => { onChanged(); closeModal?.(); };
  const remove = useArmedPress(async () => {
    const r = await removeProfile(profile.id);
    if (r?.status === 'ok') dropProfileStorage(profile.id);
    else toaster.toast({ title: 'Could not remove profile', body: r?.message || '' });
    done();
  });
  const saveName = async () => {
    const r = await renameProfile(profile.id, name);
    if (r?.status !== 'ok') toaster.toast({ title: 'Could not rename profile', body: r?.message || '' });
    done();
  };
  const unlink = async () => { await unlinkProfileSteam(profile.id); done(); };

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
              {profile.steam.length > 0 && (
                <UserMenuRow icon={<FaLink size={14} />} label={`Unlink Steam user ${profile.steam.join(', ')}`} onSelect={unlink} />
              )}
              {profile.removable && (
                <>
                  <div style={{ height: '1px', background: V2.border, margin: '4px' }} />
                  <UserMenuRow icon={<FaTrash size={14} />} danger armed={remove.armed}
                    label={remove.armed ? 'Press again to remove' : 'Remove profile'} onSelect={remove.press} />
                  <div style={{ fontSize: '11px', color: V2.fgMuted, padding: '2px 12px 8px 39px', lineHeight: 1.4 }}>
                    Its saves on RomM and its local save folder are kept.
                  </div>
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
  try {
    const list: ProfileList = await getProfiles();
    if (!list?.supported || !list.current) return;
    if (storageProfile() !== list.current) {
      swapProfileStorage(list.current);
      location.reload();
      return;
    }
    if (list.ask) showModal(<ProfilePickerModal />);
  } catch { /* single-profile shells have nothing to ask */ }
}
