% AO_ORACLE  Export the AO / AD of an MML session, and what the middle layer's
% own accessors say about every device.
%
% Writes, from one session:
%   <prefix>_ao.json      getao()  -> input of the python model
%   <prefix>_ad.json      getad(), without the Directory paths
%   <prefix>_oracle.json  per device, as returned by the middle layer:
%                         family2common, DeviceName, Status, dev2elem,
%                         getspos, family2channel, Range, HW2PhysicsParams
%                         (getfamilydata(..., DeviceList)), family2atindex
% The oracle is what compare_ao_oracle.py checks the python model against.
%
% Environment: see mml_session.m, e.g.
%   MML_ROOT=... MML_MACHINE=ALS MML_SUBMACHINE=StorageRing MML_MODE=1 \
%     matlab -batch ao_oracle

cfg = mml_session();

AO = getao;
AD = getad;
if isfield(AD, 'Directory'), AD = rmfield(AD, 'Directory'); end
mml_write_json([cfg.prefix '_ao.json'], AO);
mml_write_json([cfg.prefix '_ad.json'], AD);

oracle = struct();
oracle.machine = cfg.machine;
oracle.submachine = cfg.submachine;
oracle.operational_mode = tryget(@() getfamilydata('OperationalMode'));
oracle.energy = tryget(@() getenergy('Model'));
oracle.devices = {};
families = fieldnames(AO);
for fi = 1:numel(families)
  fam = families{fi};
  devlist = tryget(@() family2dev(fam, 0));  % all devices, also those marked bad
  if isempty(devlist) || ~isnumeric(devlist), continue, end
  for di = 1:size(devlist, 1)
    dev = devlist(di, :);
    rec = struct('family', fam, 'device', dev);
    rec.common_name = tryget(@() strtrim(family2common(fam, dev)));
    rec.device_name = tryget(@() getfamilydata(fam, 'DeviceName', dev));
    rec.status = tryget(@() getfamilydata(fam, 'Status', dev));
    rec.element = tryget(@() dev2elem(fam, dev));
    rec.position = tryget(@() getspos(fam, dev));
    rec.monitor_channel = tryget(@() strtrim(family2channel(fam, 'Monitor', dev)));
    rec.setpoint_channel = tryget(@() strtrim(family2channel(fam, 'Setpoint', dev)));
    rec.setpoint_range = tryget(@() getfamilydata(fam, 'Setpoint', 'Range', dev));
    rec.setpoint_hw_units = tryget(@() getfamilydata(fam, 'Setpoint', 'HWUnits'));
    rec.setpoint_physics_units = tryget(@() getfamilydata(fam, 'Setpoint', 'PhysicsUnits'));
    rec.setpoint_hw2physics_fcn = tryget(@() mml_sanitize(getfamilydata(fam, 'Setpoint', 'HW2PhysicsFcn')));
    rec.setpoint_hw2physics_params = tryget(@() getfamilydata(fam, 'Setpoint', 'HW2PhysicsParams', dev));
    rec.monitor_hw2physics_params = tryget(@() getfamilydata(fam, 'Monitor', 'HW2PhysicsParams', dev));
    rec.at_index = tryget(@() family2atindex(fam, dev));
    oracle.devices{end+1} = rec;
  end
end
mml_write_json([cfg.prefix '_oracle.json'], oracle);
fprintf('%s: %d families, %d devices\n', cfg.prefix, numel(families), numel(oracle.devices));

function v = tryget(f)
  try
    v = f();
  catch
    v = [];
  end
end
