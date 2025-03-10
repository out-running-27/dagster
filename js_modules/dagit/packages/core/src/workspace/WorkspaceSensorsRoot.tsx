import {gql, useQuery} from '@apollo/client';
import {Box, Colors, NonIdealState, Spinner, TextInput, Tooltip} from '@dagster-io/ui';
import * as React from 'react';

import {PYTHON_ERROR_FRAGMENT} from '../app/PythonErrorFragment';
import {FIFTEEN_SECONDS, useQueryRefreshAtInterval} from '../app/QueryRefresh';
import {useTrackPageView} from '../app/analytics';
import {useDocumentTitle} from '../hooks/useDocumentTitle';
import {useQueryPersistedState} from '../hooks/useQueryPersistedState';
import {useSelectionReducer} from '../hooks/useSelectionReducer';
import {filterPermissionedInstigationState} from '../instigation/filterPermissionedInstigationState';
import {BASIC_INSTIGATION_STATE_FRAGMENT} from '../overview/BasicInstigationStateFragment';
import {SensorBulkActionMenu} from '../sensors/SensorBulkActionMenu';
import {makeSensorKey} from '../sensors/makeSensorKey';
import {CheckAllBox} from '../ui/CheckAllBox';

import {VirtualizedSensorTable} from './VirtualizedSensorTable';
import {WorkspaceHeader} from './WorkspaceHeader';
import {repoAddressAsHumanString} from './repoAddressAsString';
import {repoAddressToSelector} from './repoAddressToSelector';
import {RepoAddress} from './types';
import {
  WorkspaceSensorsQuery,
  WorkspaceSensorsQueryVariables,
} from './types/WorkspaceSensorsRoot.types';

export const WorkspaceSensorsRoot = ({repoAddress}: {repoAddress: RepoAddress}) => {
  useTrackPageView();

  const repoName = repoAddressAsHumanString(repoAddress);
  useDocumentTitle(`Sensors: ${repoName}`);

  const selector = repoAddressToSelector(repoAddress);
  const [searchValue, setSearchValue] = useQueryPersistedState<string>({
    queryKey: 'search',
    defaults: {search: ''},
  });

  const queryResultOverview = useQuery<WorkspaceSensorsQuery, WorkspaceSensorsQueryVariables>(
    WORKSPACE_SENSORS_QUERY,
    {
      fetchPolicy: 'network-only',
      notifyOnNetworkStatusChange: true,
      variables: {selector},
    },
  );
  const {data, loading} = queryResultOverview;
  const refreshState = useQueryRefreshAtInterval(queryResultOverview, FIFTEEN_SECONDS);

  const sanitizedSearch = searchValue.trim().toLocaleLowerCase();
  const anySearch = sanitizedSearch.length > 0;

  const sensors = React.useMemo(() => {
    if (data?.repositoryOrError.__typename === 'Repository') {
      return data.repositoryOrError.sensors;
    }
    return [];
  }, [data]);

  const filteredBySearch = React.useMemo(() => {
    const searchToLower = sanitizedSearch.toLocaleLowerCase();
    return sensors.filter(({name}) => name.toLocaleLowerCase().includes(searchToLower));
  }, [sensors, sanitizedSearch]);

  const anySensorsVisible = filteredBySearch.length > 0;

  const permissionedSensors = React.useMemo(() => {
    return filteredBySearch.filter(({sensorState}) =>
      filterPermissionedInstigationState(sensorState),
    );
  }, [filteredBySearch]);

  const permissionedKeys = React.useMemo(() => {
    return permissionedSensors.map(({name}) => makeSensorKey(repoAddress, name));
  }, [permissionedSensors, repoAddress]);

  const [{checkedIds: checkedKeys}, {onToggleFactory, onToggleAll}] = useSelectionReducer(
    permissionedKeys,
  );

  const checkedSensors = React.useMemo(() => {
    return permissionedSensors
      .filter(({name}) => checkedKeys.has(makeSensorKey(repoAddress, name)))
      .map(({name, sensorState}) => {
        return {repoAddress, sensorName: name, sensorState};
      });
  }, [permissionedSensors, checkedKeys, repoAddress]);

  const permissionedCount = permissionedKeys.length;
  const checkedCount = checkedKeys.size;

  const viewerHasAnyInstigationPermission = permissionedKeys.length > 0;

  const content = () => {
    if (loading && !data) {
      return (
        <Box flex={{direction: 'row', justifyContent: 'center'}} style={{paddingTop: '100px'}}>
          <Box flex={{direction: 'row', alignItems: 'center', gap: 16}}>
            <Spinner purpose="body-text" />
            <div style={{color: Colors.Gray600}}>Loading sensors…</div>
          </Box>
        </Box>
      );
    }

    if (!filteredBySearch.length) {
      if (anySearch) {
        return (
          <Box padding={{top: 20}}>
            <NonIdealState
              icon="search"
              title="No matching sensors"
              description={
                <div>
                  No sensors matching <strong>{searchValue}</strong> were found in {repoName}
                </div>
              }
            />
          </Box>
        );
      }

      return (
        <Box padding={{top: 20}}>
          <NonIdealState
            icon="search"
            title="No sensors"
            description={`No sensors were found in ${repoName}`}
          />
        </Box>
      );
    }

    return (
      <VirtualizedSensorTable
        repoAddress={repoAddress}
        sensors={filteredBySearch}
        headerCheckbox={
          viewerHasAnyInstigationPermission ? (
            <CheckAllBox
              checkedCount={checkedCount}
              totalCount={permissionedCount}
              onToggleAll={onToggleAll}
            />
          ) : undefined
        }
        checkedKeys={checkedKeys}
        onToggleCheckFactory={onToggleFactory}
      />
    );
  };

  return (
    <Box flex={{direction: 'column'}} style={{height: '100%', overflow: 'hidden'}}>
      <WorkspaceHeader
        repoAddress={repoAddress}
        tab="sensors"
        refreshState={refreshState}
        queryData={queryResultOverview}
      />
      <Box padding={{horizontal: 24, vertical: 16}} flex={{justifyContent: 'space-between'}}>
        <TextInput
          icon="search"
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          placeholder="Filter by sensor name…"
          style={{width: '340px'}}
        />
        <Tooltip
          content="You do not have permission to start or stop these sensors"
          canShow={anySensorsVisible && !viewerHasAnyInstigationPermission}
          placement="top-end"
          useDisabledButtonTooltipFix
        >
          <SensorBulkActionMenu sensors={checkedSensors} onDone={() => refreshState.refetch()} />
        </Tooltip>
      </Box>
      {loading && !data ? (
        <Box padding={64}>
          <Spinner purpose="page" />
        </Box>
      ) : (
        content()
      )}
    </Box>
  );
};

const WORKSPACE_SENSORS_QUERY = gql`
  query WorkspaceSensorsQuery($selector: RepositorySelector!) {
    repositoryOrError(repositorySelector: $selector) {
      ... on Repository {
        id
        name
        sensors {
          id
          name
          description
          sensorState {
            id
            ...BasicInstigationStateFragment
          }
        }
      }
      ...PythonErrorFragment
    }
  }

  ${BASIC_INSTIGATION_STATE_FRAGMENT}
  ${PYTHON_ERROR_FRAGMENT}
`;
