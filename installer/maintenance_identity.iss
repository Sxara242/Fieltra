// Pure comparison: numeric release precedence, then explicit build ancestry.
// Keep unknown/unrelated builds reviewable instead of inventing their order.
function VersionKey(Version: String): String;
var
  Core, Pre, Part, Phase: String;
  Parts: TArrayOfString;
  I, P, N, Rank: Integer;
begin
  Result := '';
  Core := Version;
  Pre := '';
  P := Pos('-', Core);
  if P > 0 then begin
    Pre := Copy(Core, P + 1, Length(Core));
    Core := Copy(Core, 1, P - 1);
  end;
  Parts := StringSplit(Core, ['.'], stAll);
  if GetArrayLength(Parts) <> 3 then Exit;
  for I := 0 to 2 do begin
    Part := Parts[I];
    N := StrToIntDef(Part, -1);
    if (N < 0) or (N > 999999) or (IntToStr(N) <> Part) then begin Result := ''; Exit; end;
    Result := Result + Copy('000000', 1, 6 - Length(Part)) + Part;
  end;
  Rank := 3;
  N := 0;
  if Pre <> '' then begin
    Parts := StringSplit(Pre, ['.'], stAll);
    if GetArrayLength(Parts) <> 2 then begin Result := ''; Exit; end;
    Phase := Parts[0];
    if Phase = 'alpha' then Rank := 0
    else if Phase = 'beta' then Rank := 1
    else if Phase = 'rc' then Rank := 2
    else begin Result := ''; Exit; end;
    Part := Parts[1];
    N := StrToIntDef(Part, -1);
    if (N < 0) or (N > 999999) or (IntToStr(N) <> Part) then begin Result := ''; Exit; end;
  end
  else if P > 0 then begin Result := ''; Exit; end;
  Part := IntToStr(N);
  Result := Result + IntToStr(Rank) + Copy('000000', 1, 6 - Length(Part)) + Part;
end;

function MaintenanceModeFor(Existing: Boolean; OldVersion, OldId, OldAncestors,
  NewVersion, NewId, NewAncestors: String): String;
var OldKey, NewKey: String;
begin
  Result := 'install';
  if not Existing then Exit;
  Result := 'review';
  OldKey := VersionKey(OldVersion);
  NewKey := VersionKey(NewVersion);
  if (OldKey = '') or (NewKey = '') then Exit;
  if CompareStr(OldKey, NewKey) < 0 then Result := 'upgrade'
  else if CompareStr(OldKey, NewKey) > 0 then Result := 'downgrade'
  else if OldId <> '' then begin
    if OldId = NewId then Result := 'repair'
    else if Pos('|' + OldId + '|', NewAncestors) > 0 then Result := 'upgrade'
    else if Pos('|' + NewId + '|', OldAncestors) > 0 then Result := 'downgrade';
  end;
end;

// Execute these pure Pascal assertions in the guest before any install action.
function InitializeSetup: Boolean;
begin
  Result := False;
  if MaintenanceModeFor(False, '', '', '', '1.0.0-rc.2', 'B', '|A|') <> 'install' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.2', 'A', '', '1.0.0-rc.2', 'B', '|A|') <> 'upgrade' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.2', 'B', '|A|', '1.0.0-rc.2', 'B', '|A|') <> 'repair' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.2', 'B', '|A|', '1.0.0-rc.2', 'A', '') <> 'downgrade' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.10', '', '', '1.0.0-rc.2', 'B', '') <> 'downgrade' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.2', '', '', '1.0.0', 'B', '') <> 'upgrade' then Exit;
  if MaintenanceModeFor(True, 'unknown', '', '', '1.0.0-rc.2', 'B', '') <> 'review' then Exit;
  if MaintenanceModeFor(True, '1.0.0-rc.2', 'C', '', '1.0.0-rc.2', 'B', '|A|') <> 'review' then Exit;
  Log('Maintenance identity self-tests PASS (8 pure Pascal cases).');
  Result := True;
end;
