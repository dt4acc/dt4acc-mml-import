% AO oracle: what the facility's own middle layer says about every device,
% next to the ao / ad objects of the same session, so that the python model
% built from <prefix>_ao.json can be compared with the middle layer's own
% accessors (scripts/mml_oracle/compare_ao_oracle.py).
%
% Writes <prefix>_ao.json (getao), <prefix>_ad.json (getad, without the
% Directory paths) and <prefix>_oracle.json (per device: family2common,
% DeviceName, Status, dev2elem, getspos, family2channel, Range,
% HW2PhysicsParams, family2atindex, as returned by the middle layer).
%
% Environment:
%   MML_ROOT, MML_MACHINE, MML_SUBMACHINE  e.g. /path/to/mml ALS StorageRing
%   MML_MODE    operational mode number (setoperationalmode)
%   OUT_PREFIX  default: lower case machine name
%
%   MML_ROOT=... MML_MACHINE=ALS MML_SUBMACHINE=StorageRing MML_MODE=1 \
%     matlab -batch ao_oracle

MMLROOT = getenv('MML_ROOT');
machine = getenv('MML_MACHINE');
submachine = getenv('MML_SUBMACHINE');
mode = str2double(getenv('MML_MODE'));
prefix = getenv('OUT_PREFIX'); if isempty(prefix), prefix = lower(machine); end

% The Financial Toolbox's @drift class shadows AT's drift()
rmpath(fullfile(matlabroot, 'toolbox', 'finance', 'finsupport'));
addpath(fullfile(MMLROOT, 'mml'));
setpathmml(machine, submachine, 'StorageRing', MMLROOT);
addpath(pwd, '-begin');
if ~isnan(mode), setoperationalmode(mode); end

AO = getao;
AD = getad;
if isfield(AD, 'Directory'), AD = rmfield(AD, 'Directory'); end
write_json([prefix '_ao.json'], sanitize(AO));
write_json([prefix '_ad.json'], sanitize(AD));

oracle = struct();
oracle.machine = machine;
oracle.submachine = submachine;
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
    rec.setpoint_hw2physics_fcn = tryget(@() fcnname(getfamilydata(fam, 'Setpoint', 'HW2PhysicsFcn')));
    rec.setpoint_hw2physics_params = tryget(@() sanitize(getfamilydata(fam, 'Setpoint', 'HW2PhysicsParams', dev)));
    rec.monitor_hw2physics_params = tryget(@() sanitize(getfamilydata(fam, 'Monitor', 'HW2PhysicsParams', dev)));
    rec.at_index = tryget(@() family2atindex(fam, dev));
    oracle.devices{end+1} = rec;
  end
end
write_json([prefix '_oracle.json'], oracle);
fprintf('%s: %d families, %d devices\n', prefix, numel(families), numel(oracle.devices));

function v = tryget(f)
  try
    v = f();
  catch
    v = [];
  end
end

function s = fcnname(f)
  if isa(f, 'function_handle'), s = func2str(f); else, s = f; end
end

function v = sanitize(v)
% json encodable: function handles as their name, objects (e.g. inline) by class
  if isa(v, 'function_handle')
    v = func2str(v);
  elseif isstruct(v)
    if numel(v) ~= 1
      c = cell(1, numel(v));
      for k = 1:numel(v), c{k} = sanitize(v(k)); end
      v = c;
      return
    end
    fn = fieldnames(v);
    for k = 1:numel(fn), v.(fn{k}) = sanitize(v.(fn{k})); end
  elseif iscell(v)
    v = cellfun(@sanitize, v, 'UniformOutput', false);
  elseif isobject(v)
    v = ['<' class(v) '>'];
  end
end

function write_json(name, v)
  fid = fopen(name, 'w');
  fprintf(fid, '%s', jsonencode(v));
  fclose(fid);
end
