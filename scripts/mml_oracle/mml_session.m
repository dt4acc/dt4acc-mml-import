function cfg = mml_session()
% MML_SESSION  Start the facility's Matlab Middle Layer in one operational mode.
%
% Read from the environment:
%   MML_ROOT        root of the MML tree (the directory that contains mml/ and machine/)
%   MML_MACHINE     machine name as setpathmml expects it, e.g. ALS, MAXIV, BESSY2
%   MML_SUBMACHINE  e.g. StorageRing, R1
%   MML_MODE        operational mode number for setoperationalmode (optional)
%   OUT_PREFIX      prefix of the output files (default: lower case MML_MACHINE)
%
% The current directory is put first on the path, so that files a
% facility's lattice needs but its MML tree lacks (e.g. MAX IV: PC.mat,
% PhysConstant.m) can be placed next to these scripts.

cfg.root = getenv('MML_ROOT');
cfg.machine = getenv('MML_MACHINE');
cfg.submachine = getenv('MML_SUBMACHINE');
cfg.mode = str2double(getenv('MML_MODE'));
cfg.prefix = getenv('OUT_PREFIX');
if isempty(cfg.prefix), cfg.prefix = lower(cfg.machine); end
if isempty(cfg.root) || isempty(cfg.machine) || isempty(cfg.submachine)
  error('mml_session:config', 'set MML_ROOT, MML_MACHINE and MML_SUBMACHINE');
end

% The Financial Toolbox's @drift class shadows AT's drift(): class
% constructors take precedence over functions on the path.
finsupport = fullfile(matlabroot, 'toolbox', 'finance', 'finsupport');
if contains(path, finsupport), rmpath(finsupport); end
addpath(fullfile(cfg.root, 'mml'));
setpathmml(cfg.machine, cfg.submachine, 'StorageRing', cfg.root);
addpath(pwd, '-begin');
if ~isnan(cfg.mode), setoperationalmode(cfg.mode); end
fprintf('MML session: %s %s, operational mode %s\n', cfg.machine, cfg.submachine, ...
        char(string(getfamilydata('OperationalMode'))));
end
