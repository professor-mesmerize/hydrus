import collections
import itertools
import threading
import typing

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusTags
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusTime

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientLocation
from hydrus.client import ClientTime
from hydrus.client.metadata import ClientTags
from hydrus.client.search import ClientSearch

class FileDuplicatesManager( object ):
    
    def __init__( self, media_group_king_hash, alternates_group_id, dupe_statuses_to_counts ):
        
        self.media_group_king_hash = media_group_king_hash
        self.alternates_group_id = alternates_group_id
        self.dupe_statuses_to_count = dupe_statuses_to_counts
        
    
    def Duplicate( self ):
        
        dupe_statuses_to_count = dict( self.dupe_statuses_to_count )
        
        return FileDuplicatesManager( self.media_group_king_hash, self.alternates_group_id, dupe_statuses_to_count )
        
    
    def GetDupeCount( self, dupe_type: int ):
        
        if dupe_type not in self.dupe_statuses_to_count:
            
            return 0
            
        
        return self.dupe_statuses_to_count[ dupe_type ]
        
    
class FileInfoManager( object ):
    
    def __init__(
        self,
        hash_id: int,
        hash: bytes,
        size: typing.Optional[ int ] = None,
        mime: typing.Optional[ int ] = None,
        width: typing.Optional[ int ] = None,
        height: typing.Optional[ int ] = None,
        duration: typing.Optional[ int ] = None,
        num_frames: typing.Optional[ int ] = None,
        has_audio: typing.Optional[ bool ] = None,
        num_words: typing.Optional[ int ] = None
    ):
        
        if mime is None:
            
            mime = HC.APPLICATION_UNKNOWN
            
        
        if mime in HC.MIMES_WITH_THUMBNAILS:
            
            if width is None or width <= 0:
                
                width = 1
                
            
            if height is None or height <= 0:
                
                height = 1
                
        
        self.hash_id = hash_id
        self.hash = hash
        self.size = size
        self.mime = mime
        self.width = width
        self.height = height
        self.duration = duration
        self.num_frames = num_frames
        self.has_audio = has_audio
        self.num_words = num_words
        
        self.has_exif = False
        self.has_human_readable_embedded_metadata = False
        self.has_icc_profile = False
        
    
    def Duplicate( self ):
        
        return FileInfoManager( self.hash_id, self.hash, self.size, self.mime, self.width, self.height, self.duration, self.num_frames, self.has_audio, self.num_words )
        
    
    def ToTuple( self ):
        
        return ( self.hash_id, self.hash, self.size, self.mime, self.width, self.height, self.duration, self.num_frames, self.has_audio, self.num_words )
        
    

class TimestampsManager( object ):
    
    def __init__( self ):
        
        self._simple_timestamp_types_to_timestamps = {}
        self._domains_to_modified_timestamps = {}
        
        self._timestamp_types_to_service_keys_to_timestamps = { timestamp_type : {} for timestamp_type in ClientTime.FILE_SERVICE_TIMESTAMP_TYPES }
        
        self._canvas_types_to_last_viewed_timestamps = {}
        
        # we can complete this task and not populate the dict, so we'll handle 'did we do it?' checks with a bool, otherwise we'll loop the non-generation over and over
        self._aggregate_modified_is_generated = False
        
    
    def _ClearAggregateModifiedTimestamp( self ):
        
        if HC.TIMESTAMP_TYPE_MODIFIED_AGGREGATE in self._simple_timestamp_types_to_timestamps:
            
            del self._simple_timestamp_types_to_timestamps[ HC.TIMESTAMP_TYPE_MODIFIED_AGGREGATE ]
            
        
        self._aggregate_modified_is_generated = False
        
    
    def _ClearFileServiceTimestamp( self, timestamp_type: int, service_key: bytes ):
        
        service_keys_to_timestamps = self._timestamp_types_to_service_keys_to_timestamps[ timestamp_type ]
        
        if service_key in service_keys_to_timestamps:
            
            del service_keys_to_timestamps[ service_key ]
            
        
    
    def _ClearLastViewedTimestamp( self, canvas_type: int ):
        
        if canvas_type in self._canvas_types_to_last_viewed_timestamps:
            
            del self._canvas_types_to_last_viewed_timestamps[ canvas_type ]
            
        
    
    def _ClearSimpleTimestamp( self, timestamp_type: int ):
        
        if timestamp_type in self._simple_timestamp_types_to_timestamps:
            
            del self._simple_timestamp_types_to_timestamps[ timestamp_type ]
            
            if timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_FILE:
                
                self._ClearAggregateModifiedTimestamp()
                
            
        
    
    def _GenerateAggregateModifiedTimestamp( self ):
        
        all_timestamps = { timestamp for ( domain, timestamp ) in self._domains_to_modified_timestamps.items() }
        
        if HC.TIMESTAMP_TYPE_MODIFIED_FILE in self._simple_timestamp_types_to_timestamps:
            
            all_timestamps.add( self._simple_timestamp_types_to_timestamps[ HC.TIMESTAMP_TYPE_MODIFIED_FILE ])
            
        
        if len( all_timestamps ) > 0:
            
            self._simple_timestamp_types_to_timestamps[ HC.TIMESTAMP_TYPE_MODIFIED_AGGREGATE ] = min( all_timestamps )
            
        
        self._aggregate_modified_is_generated = True
        
    
    def _GetFileServiceTimestamp( self, timestamp_type: int, service_key: bytes ) -> typing.Optional[ int ]:
        
        return self._timestamp_types_to_service_keys_to_timestamps[ timestamp_type ].get( service_key, None )
        
    
    def _GetLastViewedTimestamp( self, canvas_type: int ) -> typing.Optional[ int ]:
        
        return self._canvas_types_to_last_viewed_timestamps.get( canvas_type, None )
        
    
    def _GetSimpleTimestamp( self, timestamp_type: int ) -> typing.Optional[ int ]:
        
        if timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_AGGREGATE and not self._aggregate_modified_is_generated:
            
            self._GenerateAggregateModifiedTimestamp()
            
        
        return self._simple_timestamp_types_to_timestamps.get( timestamp_type, None )
        
    
    def _GetDomainModifiedTimestamp( self, domain: str ):
        
        return self._domains_to_modified_timestamps.get( domain, None )
        
    
    def _SetDomainModifiedTimestamp( self, domain: str, timestamp: int ):
        
        self._domains_to_modified_timestamps[ domain ] = timestamp
        
        self._ClearAggregateModifiedTimestamp()
        
    
    def _SetFileServiceTimestamp( self, timestamp_type: int, service_key: bytes, timestamp: int ):
        
        self._timestamp_types_to_service_keys_to_timestamps[ timestamp_type ][ service_key ] = timestamp
        
    
    def _SetLastViewedTimestamp( self, canvas_type: int, timestamp: int ):
        
        self._canvas_types_to_last_viewed_timestamps[ canvas_type ] = timestamp
        
    
    def _SetSimpleTimestamp( self, timestamp_type: int, timestamp: int ):
        
        self._simple_timestamp_types_to_timestamps[ timestamp_type ] = timestamp
        
        if timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_FILE:
            
            self._ClearAggregateModifiedTimestamp()
            
        
    
    def ClearArchivedTimestamp( self ):
        
        self._ClearSimpleTimestamp( HC.TIMESTAMP_TYPE_ARCHIVED )
        
    
    def ClearDeletedTimestamp( self, service_key: bytes ):
        
        self._ClearFileServiceTimestamp( HC.TIMESTAMP_TYPE_DELETED, service_key )
        
    
    def ClearImportedTimestamp( self, service_key: bytes ):
        
        self._ClearFileServiceTimestamp( HC.TIMESTAMP_TYPE_IMPORTED, service_key )
        
    
    def ClearLastViewedTimestamp( self, canvas_type: int ):
        
        self._ClearLastViewedTimestamp( canvas_type )
        
    
    def ClearPreviouslyImportedTimestamp( self, service_key: bytes ):
        
        self._ClearFileServiceTimestamp( HC.TIMESTAMP_TYPE_PREVIOUSLY_IMPORTED, service_key )
        
    
    def ClearTimestamp( self, timestamp_data: ClientTime.TimestampData ):
        
        if timestamp_data.timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_DOMAIN:
            
            if timestamp_data.location in self._domains_to_modified_timestamps:
                
                del self._domains_to_modified_timestamps[ timestamp_data.location ]
                
                self._ClearAggregateModifiedTimestamp()
                
            
        elif timestamp_data.timestamp_type == HC.TIMESTAMP_TYPE_LAST_VIEWED:
            
            self._ClearLastViewedTimestamp( timestamp_data.location )
            
        elif timestamp_data.timestamp_type in ClientTime.FILE_SERVICE_TIMESTAMP_TYPES:
            
            self._ClearFileServiceTimestamp( timestamp_data.timestamp_type, timestamp_data.location )
            
        elif timestamp_data.timestamp_type in ClientTime.SIMPLE_TIMESTAMP_TYPES:
            
            self._ClearSimpleTimestamp( timestamp_data.timestamp_type )
            
        
    
    def Duplicate( self ) -> "TimestampsManager":
        
        timestamps_manager = TimestampsManager()
        
        timestamps_manager._simple_timestamp_types_to_timestamps = dict( self._simple_timestamp_types_to_timestamps )
        timestamps_manager._domains_to_modified_timestamps = dict( self._domains_to_modified_timestamps )
        
        return timestamps_manager
        
    
    def GetAggregateModifiedTimestamp( self ):
        
        return self._GetSimpleTimestamp( HC.TIMESTAMP_TYPE_MODIFIED_AGGREGATE )
        
    
    def GetArchivedTimestamp( self ) -> typing.Optional[ int ]:
        
        return self._GetSimpleTimestamp( HC.TIMESTAMP_TYPE_ARCHIVED )
        
    
    def GetDeletedTimestamp( self, service_key: bytes ) -> typing.Optional[ int ]:
        
        return self._GetFileServiceTimestamp( HC.TIMESTAMP_TYPE_DELETED, service_key )
        
    
    def GetDomainModifiedTimestamp( self, domain: str ) -> typing.Optional[ int ]:
        
        return self._GetDomainModifiedTimestamp( domain )
        
    
    def GetDomainModifiedTimestamps( self ) -> typing.Dict[ str, int ]:
        
        return dict( self._domains_to_modified_timestamps )
        
    
    def GetDomainModifiedTimestampDatas( self ) -> typing.Collection[ ClientTime.TimestampData ]:
        
        return [ ClientTime.TimestampData( timestamp_type = HC.TIMESTAMP_TYPE_MODIFIED_DOMAIN, location = domain, timestamp = timestamp ) for ( domain, timestamp ) in self._domains_to_modified_timestamps.items() ]
        
    
    def GetFileModifiedTimestamp( self ) -> typing.Optional[ int ]:
        
        return self._GetSimpleTimestamp( HC.TIMESTAMP_TYPE_MODIFIED_FILE )
        
    
    def GetFileServiceTimestampDatas( self ) -> typing.Collection[ ClientTime.TimestampData ]:
        
        result = []
        
        for ( timestamp_type, service_keys_to_timestamps ) in self._timestamp_types_to_service_keys_to_timestamps.items():
            
            for ( service_key, timestamp ) in service_keys_to_timestamps.items():
                
                result.append( ClientTime.TimestampData( timestamp_type = timestamp_type, location = service_key, timestamp = timestamp ) )
                
            
        
        return result
        
    
    def GetImportedTimestamp( self, service_key: bytes ) -> typing.Optional[ int ]:
        
        return self._GetFileServiceTimestamp( HC.TIMESTAMP_TYPE_IMPORTED, service_key )
        
    
    def GetLastViewedTimestamp( self, canvas_type ):
        
        return self._GetLastViewedTimestamp( canvas_type )
        
    
    def GetPreviouslyImportedTimestamp( self, service_key: bytes ) -> typing.Optional[ int ]:
        
        return self._GetFileServiceTimestamp( HC.TIMESTAMP_TYPE_PREVIOUSLY_IMPORTED, service_key )
        
    
    def GetTimestampFromStub( self, timestamp_data_stub: ClientTime.TimestampData ) -> typing.Optional[ int ]:
        
        if timestamp_data_stub.timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_DOMAIN:
            
            if timestamp_data_stub.location is None:
                
                return None
                
            
            return self._GetDomainModifiedTimestamp( timestamp_data_stub.location )
            
        elif timestamp_data_stub.timestamp_type == HC.TIMESTAMP_TYPE_LAST_VIEWED:
            
            if timestamp_data_stub.location is None:
                
                return None
                
            
            return self._GetLastViewedTimestamp( timestamp_data_stub.location )
            
        elif timestamp_data_stub.timestamp_type in ClientTime.FILE_SERVICE_TIMESTAMP_TYPES:
            
            if timestamp_data_stub.location is None:
                
                return None
                
            
            return self._GetFileServiceTimestamp( timestamp_data_stub.timestamp_type, timestamp_data_stub.location )
            
        elif timestamp_data_stub.timestamp_type in ClientTime.SIMPLE_TIMESTAMP_TYPES:
            
            return self._GetSimpleTimestamp( timestamp_data_stub.timestamp_type )
            
        
        return None
        
    
    def SetArchivedTimestamp( self, timestamp: int ):
        
        self._SetSimpleTimestamp( HC.TIMESTAMP_TYPE_ARCHIVED, timestamp )
        
    
    def SetDeletedTimestamp( self, service_key: bytes, timestamp: int ):
        
        self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_DELETED, service_key, timestamp )
        
    
    def SetDeletedTimestamps( self, service_keys_to_timestamps: typing.Dict[ bytes, int ] ):
        
        for ( service_key, timestamp ) in service_keys_to_timestamps.items():
            
            self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_DELETED, service_key, timestamp )
            
        
    
    def SetDomainModifiedTimestamp( self, domain: str, timestamp: int ):
        
        self._SetDomainModifiedTimestamp( domain, timestamp )
        
    
    def SetFileModifiedTimestamp( self, timestamp: int ):
        
        self._SetSimpleTimestamp( HC.TIMESTAMP_TYPE_MODIFIED_FILE, timestamp )
        
    
    def SetLastViewedTimestamp( self, canvas_type, timestamp ):
        
        self._SetLastViewedTimestamp( canvas_type, timestamp )
        
    
    def SetPreviouslyImportedTimestamp( self, service_key, timestamp ):
        
        self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_PREVIOUSLY_IMPORTED, service_key, timestamp )
        
    
    def SetPreviouslyImportedTimestamps( self, service_keys_to_timestamps: typing.Dict[ bytes, int ] ):
        
        for ( service_key, timestamp ) in service_keys_to_timestamps.items():
            
            self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_PREVIOUSLY_IMPORTED, service_key, timestamp )
            
        
    
    def SetImportedTimestamp( self, service_key: bytes, timestamp: int ):
        
        self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_IMPORTED, service_key, timestamp )
        
    
    def SetImportedTimestamps( self, service_keys_to_timestamps: typing.Dict[ bytes, int ] ):
        
        for ( service_key, timestamp ) in service_keys_to_timestamps.items():
            
            self._SetFileServiceTimestamp( HC.TIMESTAMP_TYPE_IMPORTED, service_key, timestamp )
            
        
    
    def SetTimestamp( self, timestamp_data: ClientTime.TimestampData ):
        
        if timestamp_data.timestamp is None:
            
            return
            
        
        if timestamp_data.timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_DOMAIN:
            
            if timestamp_data.location is None:
                
                return
                
            
            self._SetDomainModifiedTimestamp( timestamp_data.location, timestamp_data.timestamp )
            
        elif timestamp_data.timestamp_type == HC.TIMESTAMP_TYPE_LAST_VIEWED:
            
            if timestamp_data.location is None:
                
                return
                
            
            self._SetLastViewedTimestamp( timestamp_data.location, timestamp_data.timestamp )
            
        elif timestamp_data.timestamp_type in ClientTime.FILE_SERVICE_TIMESTAMP_TYPES:
            
            if timestamp_data.location is None:
                
                return
                
            
            self._SetFileServiceTimestamp( timestamp_data.timestamp_type, timestamp_data.location, timestamp_data.timestamp )
            
        elif timestamp_data.timestamp_type in ClientTime.SIMPLE_TIMESTAMP_TYPES:
            
            self._SetSimpleTimestamp( timestamp_data.timestamp_type, timestamp_data.timestamp )
            
        
    
    def UpdateTimestamp( self, timestamp_data: ClientTime.TimestampData ):
        
        if timestamp_data.timestamp is None:
            
            return
            
        
        if timestamp_data.timestamp_type == HC.TIMESTAMP_TYPE_MODIFIED_DOMAIN:
            
            existing_timestamp = self._GetDomainModifiedTimestamp( timestamp_data.location )
            
        else:
            
            existing_timestamp = self._GetSimpleTimestamp( timestamp_data.timestamp_type )
            
        
        if existing_timestamp is None or ClientTime.ShouldUpdateModifiedTime( existing_timestamp, timestamp_data.timestamp ):
            
            self.SetTimestamp( timestamp_data )
            
        
    

class FileViewingStatsManager( object ):
    
    def __init__(
        self,
        timestamps_manager: TimestampsManager,
        view_rows: typing.Collection
    ):
        
        self._timestamps_manager = timestamps_manager
        
        self.views = collections.Counter()
        self.viewtimes = collections.Counter()
        
        for ( canvas_type, last_viewed_timestamp, views, viewtime ) in view_rows:
            
            if last_viewed_timestamp is not None:
                
                self._timestamps_manager.SetLastViewedTimestamp( canvas_type, last_viewed_timestamp )
                
            
            if views != 0:
                
                self.views[ canvas_type ] = views
                
            
            if viewtime != 0:
                
                self.viewtimes[ canvas_type ] = viewtime
                
            
        
    
    def Duplicate( self, timestamps_manager: TimestampsManager ) -> "FileViewingStatsManager":
        
        view_rows = []
        
        for canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_PREVIEW ):
            
            last_viewed_timestamp = self._timestamps_manager.GetLastViewedTimestamp( canvas_type )
            
            views = self.views[ canvas_type ]
            viewtime = self.viewtimes[ canvas_type ]
            
            view_rows.append( ( canvas_type, last_viewed_timestamp, views, viewtime ) )
            
        
        return FileViewingStatsManager( timestamps_manager, view_rows )
        
    
    def GetPrettyViewsLine( self, canvas_types: typing.Collection[ int ] ) -> str:
        
        if len( canvas_types ) == 2:
            
            info_string = ''
            
        elif CC.CANVAS_MEDIA_VIEWER in canvas_types:
            
            info_string = ' in media viewer'
            
        elif CC.CANVAS_PREVIEW in canvas_types:
            
            info_string = ' in preview window'
            
        
        views_total = sum( ( self.views[ canvas_type ] for canvas_type in canvas_types ) )
        viewtime_total = sum( ( self.viewtimes[ canvas_type ] for canvas_type in canvas_types ) )
        
        if views_total == 0:
            
            return 'no view record{}'.format( info_string )
            
        
        last_viewed_times = []
        
        for canvas_type in canvas_types:
            
            last_viewed_time = self._timestamps_manager.GetLastViewedTimestamp( canvas_type )
            
            if last_viewed_time is not None:
                
                last_viewed_times.append( last_viewed_time )
                
            
        
        if len( last_viewed_times ) == 0:
            
            last_viewed_string = 'no recorded last view time'
            
        else:
            
            last_viewed_string = 'last {}'.format( HydrusTime.TimestampToPrettyTimeDelta( max( last_viewed_times ) ) )
            
        
        return 'viewed {} times{}, totalling {}, {}'.format( HydrusData.ToHumanInt( views_total ), info_string, HydrusTime.TimeDeltaToPrettyTimeDelta( viewtime_total ), last_viewed_string )
        
    
    def GetTimestampsManager( self ) -> TimestampsManager:
        
        return self._timestamps_manager
        
    
    def GetViews( self, canvas_type: int ) -> int:
        
        return self.views[ canvas_type ]
        
    
    def GetViewtime( self, canvas_type: int ) -> int:
        
        return self.viewtimes[ canvas_type ]
        
    
    def MergeCounts( self, file_viewing_stats_manager: "FileViewingStatsManager" ):
        
        for canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_PREVIEW ):
            
            timestamps = { self._timestamps_manager.GetLastViewedTimestamp( canvas_type ), file_viewing_stats_manager.GetTimestampsManager().GetLastViewedTimestamp( canvas_type ) }
            
            timestamps.discard( None )
            
            if len( timestamps ) > 0:
                
                last_viewed_timestamp = max( timestamps )
                
                self._timestamps_manager.SetLastViewedTimestamp( canvas_type, last_viewed_timestamp )
                
            
        
        self.views.update( file_viewing_stats_manager.views )
        self.viewtimes.update( file_viewing_stats_manager.viewtimes )
        
    
    def ProcessContentUpdate( self, content_update ):
        
        ( data_type, action, row ) = content_update.ToTuple()
        
        if action == HC.CONTENT_UPDATE_ADD:
            
            ( hash, canvas_type, view_timestamp, views_delta, viewtime_delta ) = row
            
            if view_timestamp is not None:
                
                self._timestamps_manager.SetLastViewedTimestamp( canvas_type, view_timestamp )
                
            
            self.views[ canvas_type ] += views_delta
            self.viewtimes[ canvas_type ] += viewtime_delta
            
        elif action == HC.CONTENT_UPDATE_DELETE:
            
            self._timestamps_manager.ClearLastViewedTimestamp( CC.CANVAS_MEDIA_VIEWER )
            self._timestamps_manager.ClearLastViewedTimestamp( CC.CANVAS_PREVIEW )
            
            self.views = collections.Counter()
            self.viewtimes = collections.Counter()
            
        
    
    @staticmethod
    def STATICGenerateCombinedManager( sub_fvsms: typing.Iterable[ "FileViewingStatsManager" ] ):
        
        fvsm = FileViewingStatsManager.STATICGenerateEmptyManager( TimestampsManager() )
        
        for sub_fvsm in sub_fvsms:
            
            fvsm.MergeCounts( sub_fvsm )
            
        
        return fvsm
        
    
    @staticmethod
    def STATICGenerateEmptyManager( timestamps_manager: TimestampsManager ):
        
        return FileViewingStatsManager( timestamps_manager, [] )
        
    

class LocationsManager( object ):
    
    def __init__(
        self,
        current: typing.Set[ bytes ],
        deleted: typing.Set[ bytes ],
        pending: typing.Set[ bytes ],
        petitioned: typing.Set[ bytes ],
        timestamps_manager: TimestampsManager,
        inbox: bool = False,
        urls: typing.Optional[ typing.Set[ str ] ] = None,
        service_keys_to_filenames: typing.Optional[ typing.Dict[ bytes, str ] ] = None,
        local_file_deletion_reason: str = None
    ):
        
        self._current = current
        self._deleted = deleted
        self._pending = pending
        self._petitioned = petitioned
        self._timestamps_manager = timestamps_manager
        
        self.inbox = inbox
        
        if urls is None:
            
            urls = set()
            
        
        self._urls = urls
        
        if service_keys_to_filenames is None:
            
            service_keys_to_filenames = {}
            
        
        self._service_keys_to_filenames = service_keys_to_filenames
        
        self._local_file_deletion_reason = local_file_deletion_reason
        
    
    def _AddToService( self, service_key, do_undelete = False, forced_import_time = None ):
        
        service_type = HG.client_controller.services_manager.GetServiceType( service_key )
        
        if forced_import_time is None:
            
            import_time = HydrusTime.GetNow()
            
        else:
            
            import_time = forced_import_time
            
        
        if service_key in self._deleted:
            
            if do_undelete:
                
                previously_imported_time = self._timestamps_manager.GetPreviouslyImportedTimestamp( service_key )
                
                if previously_imported_time is not None:
                    
                    import_time = previously_imported_time
                    
                
            
            self._timestamps_manager.ClearDeletedTimestamp( service_key )
            self._timestamps_manager.ClearPreviouslyImportedTimestamp( service_key )
            
            self._deleted.discard( service_key )
            
        else:
            
            if do_undelete:
                
                # was never deleted from here, so no undelete to do!
                return
                
            
        
        local_service_keys = HG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, ) )
        
        if service_key in local_service_keys:
            
            if CC.TRASH_SERVICE_KEY in self._current:
                
                self._timestamps_manager.ClearImportedTimestamp( CC.TRASH_SERVICE_KEY )
                
                self._current.discard( CC.TRASH_SERVICE_KEY )
                
            
            # forced import time here to handle do_undelete, ensuring old timestamp is propagated
            
            self._AddToService( CC.COMBINED_LOCAL_MEDIA_SERVICE_KEY, forced_import_time = import_time )
            self._AddToService( CC.COMBINED_LOCAL_FILE_SERVICE_KEY, forced_import_time = import_time )
            
        
        if service_key not in self._current:
            
            self._timestamps_manager.SetImportedTimestamp( service_key, import_time )
            
            self._current.add( service_key )
            
            if service_key == CC.COMBINED_LOCAL_FILE_SERVICE_KEY:
                
                self.inbox = True
                
            
        
        self._pending.discard( service_key )
        
        if service_type in HC.FILE_SERVICES_COVERED_BY_COMBINED_DELETED_FILE:
            
            all_service_keys_covered_by_combined_deleted_files = HG.client_controller.services_manager.GetServiceKeys( HC.FILE_SERVICES_COVERED_BY_COMBINED_DELETED_FILE )
            
            if len( self._deleted.intersection( all_service_keys_covered_by_combined_deleted_files ) ) == 0:
                
                self._DeleteFromService( CC.COMBINED_DELETED_FILE_SERVICE_KEY, None )
                
            
        
    
    def _DeleteFromService( self, service_key: bytes, reason: typing.Optional[ str ] ):
        
        service_type = HG.client_controller.services_manager.GetServiceType( service_key )
        
        if service_key in self._current:
            
            previously_imported_timestamp = self._timestamps_manager.GetImportedTimestamp( service_key )
            
            self._timestamps_manager.ClearImportedTimestamp( service_key )
            
            self._current.discard( service_key )
            
        else:
            
            previously_imported_timestamp = None
            
        
        if service_type in HC.FILE_SERVICES_COVERED_BY_COMBINED_DELETED_FILE:
            
            self._AddToService( CC.COMBINED_DELETED_FILE_SERVICE_KEY )
            
        
        make_a_delete_record = service_key not in self._deleted and service_type not in HC.FILE_SERVICES_WITH_NO_DELETE_RECORD
        
        if make_a_delete_record:
            
            self._timestamps_manager.SetDeletedTimestamp( service_key, HydrusTime.GetNow() )
            self._timestamps_manager.SetPreviouslyImportedTimestamp( service_key, previously_imported_timestamp )
            
            self._deleted.add( service_key )
            
        
        self._petitioned.discard( service_key )
        
        local_service_keys = HG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, ) )
        
        if service_key in local_service_keys:
            
            if reason is not None:
                
                self._local_file_deletion_reason = reason
                
            
            not_in_a_local_service_any_more = self._current.isdisjoint( local_service_keys )
            
            if not_in_a_local_service_any_more:
                
                self._DeleteFromService( CC.COMBINED_LOCAL_MEDIA_SERVICE_KEY, reason )
                self._AddToService( CC.TRASH_SERVICE_KEY )
                
            
        elif service_key == CC.COMBINED_LOCAL_FILE_SERVICE_KEY:
            
            for local_service_key in list( self._current.intersection( local_service_keys ) ):
                
                self._DeleteFromService( local_service_key, reason )
                
            
            if CC.TRASH_SERVICE_KEY in self._current:
                
                self._DeleteFromService( CC.TRASH_SERVICE_KEY, reason )
                
            
            self.inbox = False
            
        
    
    def DeletePending( self, service_key ):
        
        self._pending.discard( service_key )
        self._petitioned.discard( service_key )
        
    
    def Duplicate( self, timestamps_manager: TimestampsManager ):
        
        current = set( self._current )
        deleted = set( self._deleted )
        pending = set( self._pending )
        petitioned = set( self._petitioned )
        urls = set( self._urls )
        service_keys_to_filenames = dict( self._service_keys_to_filenames )
        
        return LocationsManager(
            current,
            deleted,
            pending,
            petitioned,
            timestamps_manager,
            inbox = self.inbox,
            urls = urls,
            service_keys_to_filenames = service_keys_to_filenames,
            local_file_deletion_reason = self._local_file_deletion_reason
        )
        
    
    def GetCDPP( self ):
        
        return ( self._current, self._deleted, self._pending, self._petitioned )
        
    
    def GetCurrent( self ):
        
        return self._current
        
    
    def GetDeleted( self ):
        
        return self._deleted
        
    
    def GetInbox( self ):
        
        return self.inbox
        
    
    def GetPending( self ):
        
        return self._pending
        
    
    def GetPetitioned( self ):
        
        return self._petitioned
        
    
    def GetRemoteLocationStrings( self ):
        
        remote_file_services = list( HG.client_controller.services_manager.GetServices( ( HC.FILE_REPOSITORY, HC.IPFS ) ) )
        
        remote_file_services.sort( key = lambda s: s.GetName() )
        
        remote_service_strings = []
        
        for remote_service in remote_file_services:
            
            name = remote_service.GetName()
            service_key = remote_service.GetServiceKey()
            
            if service_key in self._pending:
                
                remote_service_strings.append( name + ' (+)' )
                
            elif service_key in self._current:
                
                if service_key in self._petitioned:
                    
                    remote_service_strings.append( name + ' (-)' )
                    
                else:
                    
                    remote_service_strings.append( name )
                    
                
            
        
        return remote_service_strings
        
    
    def GetBestCurrentTimestamp( self, location_context: ClientLocation.LocationContext ):
        
        timestamps = { self._timestamps_manager.GetImportedTimestamp( service_key ) for service_key in location_context.current_service_keys }
        
        timestamps.discard( None )
        
        if len( timestamps ) == 0:
            
            return None
            
        else:
            
            return min( timestamps )
            
        
    
    def GetLocalFileDeletionReason( self ) -> str:
        
        if self._local_file_deletion_reason is None:
            
            return 'Unknown deletion reason.'
            
        else:
            
            return self._local_file_deletion_reason
            
        
    
    def GetServiceFilename( self, service_key ) -> typing.Optional[ str ]:
        
        if service_key in self._service_keys_to_filenames:
            
            return self._service_keys_to_filenames[ service_key ]
            
        else:
            
            return None
            
        
    
    def GetServiceFilenames( self ) -> typing.Dict[ bytes, str ]:
        
        return dict( self._service_keys_to_filenames )
        
    
    def GetTimestampsManager( self ) -> TimestampsManager:
        
        return self._timestamps_manager
        
    
    def GetURLs( self ):
        
        return self._urls
        
    
    def HasLocalFileDeletionReason( self ) -> bool:
        
        return self._local_file_deletion_reason is not None
        
    
    def IsDownloading( self ):
        
        return CC.COMBINED_LOCAL_FILE_SERVICE_KEY in self._pending
        
    
    def IsLocal( self ):
        
        return CC.COMBINED_LOCAL_FILE_SERVICE_KEY in self._current
        
    
    def IsRemote( self ):
        
        return CC.COMBINED_LOCAL_FILE_SERVICE_KEY not in self._current
        
    
    def IsTrashed( self ):
        
        return CC.TRASH_SERVICE_KEY in self._current
        
    
    def ProcessContentUpdate( self, service_key, content_update ):
        
        ( data_type, action, row ) = content_update.ToTuple()
        
        if data_type == HC.CONTENT_TYPE_FILES:
            
            if action == HC.CONTENT_UPDATE_CLEAR_DELETE_RECORD:
                
                if service_key in self._deleted:
                    
                    if service_key == CC.COMBINED_LOCAL_FILE_SERVICE_KEY:
                        
                        service_keys = HG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, HC.COMBINED_LOCAL_FILE ) )
                        
                    else:
                        
                        service_keys = ( service_key, )
                        
                    
                    for service_key in service_keys:
                        
                        self._timestamps_manager.ClearDeletedTimestamp( service_key )
                        self._timestamps_manager.ClearPreviouslyImportedTimestamp( service_key )
                        
                        self._deleted.discard( service_key )
                        
                    
                
            elif action == HC.CONTENT_UPDATE_ARCHIVE:
                
                if self.inbox:
                    
                    self.inbox = False
                    
                    self._timestamps_manager.SetArchivedTimestamp( HydrusTime.GetNow() )
                    
                
            elif action == HC.CONTENT_UPDATE_INBOX:
                
                self.inbox = True
                
                self._timestamps_manager.ClearArchivedTimestamp()
                
            elif action == HC.CONTENT_UPDATE_ADD:
                
                self._AddToService( service_key )
                
            elif action == HC.CONTENT_UPDATE_DELETE:
                
                if content_update.HasReason():
                    
                    reason = content_update.GetReason()
                    
                else:
                    
                    reason = None
                    
                
                if service_key == CC.COMBINED_LOCAL_MEDIA_SERVICE_KEY:
                    
                    for s_k in HG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, ) ):
                        
                        if s_k in self._current:
                            
                            self._DeleteFromService( s_k, reason )
                            
                        
                    
                else:
                    
                    self._DeleteFromService( service_key, reason )
                    
                
            elif action == HC.CONTENT_UPDATE_UNDELETE:
                
                if service_key == CC.COMBINED_LOCAL_MEDIA_SERVICE_KEY:
                    
                    for s_k in HG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, ) ):
                        
                        if s_k in self._deleted:
                            
                            self._AddToService( s_k, do_undelete = True )
                            
                        
                    
                else:
                    
                    self._AddToService( service_key, do_undelete = True )
                    
                
            elif action == HC.CONTENT_UPDATE_PEND:
                
                if service_key not in self._current:
                    
                    self._pending.add( service_key )
                    
                
            elif action == HC.CONTENT_UPDATE_PETITION:
                
                if service_key not in self._deleted:
                    
                    self._petitioned.add( service_key )
                    
                
            elif action == HC.CONTENT_UPDATE_RESCIND_PEND:
                
                self._pending.discard( service_key )
                
            elif action == HC.CONTENT_UPDATE_RESCIND_PETITION:
                
                self._petitioned.discard( service_key )
                
            
        elif data_type == HC.CONTENT_TYPE_URLS:
            
            if action == HC.CONTENT_UPDATE_ADD:
                
                ( urls, hashes ) = row
                
                self._urls.update( urls )
                
            elif action == HC.CONTENT_UPDATE_DELETE:
                
                ( urls, hashes ) = row
                
                self._urls.difference_update( urls )
                
                
            
        elif data_type == HC.CONTENT_TYPE_TIMESTAMP:
            
            ( hash, timestamp_data ) = row
            
            if action == HC.CONTENT_UPDATE_ADD:
                
                self._timestamps_manager.UpdateTimestamp( timestamp_data )
                
            elif action == HC.CONTENT_UPDATE_SET:
                
                self._timestamps_manager.SetTimestamp( timestamp_data )
                
            elif action == HC.CONTENT_UPDATE_DELETE:
                
                self._timestamps_manager.ClearTimestamp( timestamp_data )
                
            
        
    
    def ResetService( self, service_key ):
        
        self._timestamps_manager.ClearImportedTimestamp( service_key )
        self._timestamps_manager.ClearDeletedTimestamp( service_key )
        self._timestamps_manager.ClearPreviouslyImportedTimestamp( service_key )
        
        self._current.discard( service_key )
        self._deleted.discard( service_key )
        self._pending.discard( service_key )
        self._petitioned.discard( service_key )
        
    
class NotesManager( object ):
    
    def __init__( self, names_to_notes: typing.Dict[ str, str ] ):
        
        self._names_to_notes = names_to_notes
        
    
    def Duplicate( self ):
        
        return NotesManager( dict( self._names_to_notes ) )
        
    
    def GetNames( self ):
        
        names = sorted( self._names_to_notes.keys() )
        
        return names
        
    
    def GetNamesToNotes( self ):
        
        return dict( self._names_to_notes )
        
    
    def SetNamesToNotes( self, names_to_notes: typing.Dict[ str, str ] ):
        
        self._names_to_notes = names_to_notes
        
    
    def GetNote( self, name: str ):
        
        if name in self._names_to_notes:
            
            return self._names_to_notes[ name ]
            
        else:
            
            raise HydrusExceptions.DataMissing( 'Note "{}" does not exist!'.format( name ) )
            
        
    
    def GetNumNotes( self ):
        
        return len( self._names_to_notes )
        
    
    def HasNote( self, name: str ):
        
        return name in self._names_to_notes
        
    
    def ProcessContentUpdate( self, content_update ):
        
        ( data_type, action, row ) = content_update.ToTuple()
        
        if action == HC.CONTENT_UPDATE_SET:
            
            ( hash, name, note ) = row
            
            if note == '':
                
                if name in self._names_to_notes:
                    
                    del self._names_to_notes[ name ]
                    
                
            else:
                
                self._names_to_notes[ name ] = note
                
            
        elif action == HC.CONTENT_UPDATE_DELETE:
            
            ( hash, name ) = row
            
            if name in self._names_to_notes:
                
                del self._names_to_notes[ name ]
                
            
        
    
class RatingsManager( object ):
    
    def __init__( self, service_keys_to_ratings: typing.Dict[ bytes, typing.Union[ None, float ] ] ):
        
        self._service_keys_to_ratings = service_keys_to_ratings
        
    
    def Duplicate( self ):
        
        return RatingsManager( dict( self._service_keys_to_ratings ) )
        
    
    def GetRating( self, service_key ):
        
        if service_key in self._service_keys_to_ratings:
            
            return self._service_keys_to_ratings[ service_key ]
            
        else:
            
            service_type = HG.client_controller.services_manager.GetServiceType( service_key )
            
            if service_type == HC.LOCAL_RATING_INCDEC:
                
                return 0
                
            else:
                
                return None
                
            
        
    
    def GetStarRatingSlice( self, service_keys ):
        
        return frozenset( { self._service_keys_to_ratings[ service_key ] for service_key in service_keys if service_key in self._service_keys_to_ratings } )
        
    
    def ProcessContentUpdate( self, service_key, content_update ):
        
        ( data_type, action, row ) = content_update.ToTuple()
        
        if action == HC.CONTENT_UPDATE_ADD:
            
            ( rating, hashes ) = row
            
            if rating is None and service_key in self._service_keys_to_ratings:
                
                del self._service_keys_to_ratings[ service_key ]
                
            else:
                
                self._service_keys_to_ratings[ service_key ] = rating
                
            
        
    
    def ResetService( self, service_key ):
        
        if service_key in self._service_keys_to_ratings:
            
            del self._service_keys_to_ratings[ service_key ]
            
        
    

class TagsManager( object ):
    
    def __init__(
        self,
        service_keys_to_statuses_to_storage_tags: typing.Dict[ bytes, typing.Dict[ int, typing.Set[ str ] ] ],
        service_keys_to_statuses_to_display_tags: typing.Dict[ bytes, typing.Dict[ int, typing.Set[ str ] ] ]
        ):
        
        self._tag_display_types_to_service_keys_to_statuses_to_tags = {
            ClientTags.TAG_DISPLAY_STORAGE : service_keys_to_statuses_to_storage_tags,
            ClientTags.TAG_DISPLAY_ACTUAL : service_keys_to_statuses_to_display_tags
        }
        
        self._storage_cache_is_dirty = True
        self._display_cache_is_dirty = True
        self._single_media_cache_is_dirty = True
        self._selection_list_cache_is_dirty = True
        
        self._lock = threading.Lock()
        
    
    def _GetServiceKeysToStatusesToTags( self, tag_display_type ):
        
        # this gets called a lot, so we are hardcoding some gubbins to avoid too many method calls
        
        if tag_display_type == ClientTags.TAG_DISPLAY_STORAGE and self._storage_cache_is_dirty:
            
            self._RecalcStorageCache()
            
        if tag_display_type == ClientTags.TAG_DISPLAY_ACTUAL and self._display_cache_is_dirty:
            
            self._RecalcDisplayCache()
            
        elif tag_display_type == ClientTags.TAG_DISPLAY_SELECTION_LIST and self._selection_list_cache_is_dirty:
            
            self._RecalcDisplayFilteredCache( ClientTags.TAG_DISPLAY_SELECTION_LIST )
            
        elif tag_display_type == ClientTags.TAG_DISPLAY_SINGLE_MEDIA and self._single_media_cache_is_dirty:
            
            self._RecalcDisplayFilteredCache( ClientTags.TAG_DISPLAY_SINGLE_MEDIA )
            
        
        return self._tag_display_types_to_service_keys_to_statuses_to_tags[ tag_display_type ]
        
    
    def _RecalcStorageCache( self ):
        
        service_keys_to_statuses_to_tags = self._tag_display_types_to_service_keys_to_statuses_to_tags[ ClientTags.TAG_DISPLAY_STORAGE ]
        
        # just combined service merge calculation
        
        combined_statuses_to_tags = HydrusData.default_dict_set()
        
        for ( service_key, source_statuses_to_tags ) in service_keys_to_statuses_to_tags.items():
            
            if service_key == CC.COMBINED_TAG_SERVICE_KEY:
                
                continue
                
            
            for ( status, tags ) in source_statuses_to_tags.items():
                
                combined_statuses_to_tags[ status ].update( tags )
                
            
        
        service_keys_to_statuses_to_tags[ CC.COMBINED_TAG_SERVICE_KEY ] = combined_statuses_to_tags
        
        #
        
        self._storage_cache_is_dirty = False
        
    
    def _RecalcDisplayCache( self ):
        
        if self._storage_cache_is_dirty:
            
            self._RecalcStorageCache()
            
        
        # display tags don't have petitioned or deleted, so we just copy from storage
        
        source_service_keys_to_statuses_to_tags = self._tag_display_types_to_service_keys_to_statuses_to_tags[ ClientTags.TAG_DISPLAY_STORAGE ]
        
        destination_service_keys_to_statuses_to_tags = self._tag_display_types_to_service_keys_to_statuses_to_tags[ ClientTags.TAG_DISPLAY_ACTUAL ]
        
        combined_statuses_to_tags = HydrusData.default_dict_set()
        
        for ( service_key, source_statuses_to_tags ) in source_service_keys_to_statuses_to_tags.items():
            
            if service_key == CC.COMBINED_TAG_SERVICE_KEY:
                
                continue
                
            
            destination_statuses_to_tags = destination_service_keys_to_statuses_to_tags[ service_key ]
            
            for status in ( HC.CONTENT_STATUS_DELETED, HC.CONTENT_STATUS_PETITIONED ):
                
                if status in destination_statuses_to_tags:
                    
                    del destination_statuses_to_tags[ status ]
                    
                
                if status in source_statuses_to_tags:
                    
                    destination_statuses_to_tags[ status ] = set( source_statuses_to_tags[ status ] )
                    
                
            
            for ( status, tags ) in destination_statuses_to_tags.items():
                
                combined_statuses_to_tags[ status ].update( tags )
                
            
        
        destination_service_keys_to_statuses_to_tags[ CC.COMBINED_TAG_SERVICE_KEY ] = combined_statuses_to_tags
        
        #
        
        self._display_cache_is_dirty = False
        
    
    def _RecalcDisplayFilteredCache( self, tag_display_type ):
        
        if self._display_cache_is_dirty:
            
            self._RecalcDisplayCache()
            
        
        # display filtering
        
        tag_display_manager = HG.client_controller.tag_display_manager
        
        source_service_keys_to_statuses_to_tags = self._tag_display_types_to_service_keys_to_statuses_to_tags[ ClientTags.TAG_DISPLAY_ACTUAL ]
        
        destination_service_keys_to_statuses_to_tags = collections.defaultdict( HydrusData.default_dict_set )
        
        combined_statuses_to_tags = HydrusData.default_dict_set()
        
        for ( service_key, source_statuses_to_tags ) in source_service_keys_to_statuses_to_tags.items():
            
            if service_key == CC.COMBINED_TAG_SERVICE_KEY:
                
                continue
                
            
            if tag_display_manager.FiltersTags( tag_display_type, service_key ):
                
                destination_statuses_to_tags = HydrusData.default_dict_set()
                
                for ( status, source_tags ) in source_statuses_to_tags.items():
                    
                    dest_tags = tag_display_manager.FilterTags( tag_display_type, service_key, source_tags )
                    
                    if len( source_tags ) != len( dest_tags ):
                        
                        if len( dest_tags ) > 0:
                            
                            destination_statuses_to_tags[ status ] = dest_tags
                            
                        
                    else:
                        
                        destination_statuses_to_tags[ status ] = source_tags
                        
                    
                
            else:
                
                destination_statuses_to_tags = source_statuses_to_tags
                
            
            destination_service_keys_to_statuses_to_tags[ service_key ] = destination_statuses_to_tags
            
            for ( status, tags ) in destination_statuses_to_tags.items():
                
                combined_statuses_to_tags[ status ].update( tags )
                
            
        
        destination_service_keys_to_statuses_to_tags[ CC.COMBINED_TAG_SERVICE_KEY ] = combined_statuses_to_tags
        
        self._tag_display_types_to_service_keys_to_statuses_to_tags[ tag_display_type ] = destination_service_keys_to_statuses_to_tags
        
        #
        
        if tag_display_type == ClientTags.TAG_DISPLAY_SELECTION_LIST:
            
            self._selection_list_cache_is_dirty = False
            
        elif tag_display_type == ClientTags.TAG_DISPLAY_SINGLE_MEDIA:
            
            self._single_media_cache_is_dirty = False
            
        
    
    def _SetDirty( self ):
        
        self._storage_cache_is_dirty = True
        self._display_cache_is_dirty = True
        self._single_media_cache_is_dirty = True
        self._selection_list_cache_is_dirty = True
        
    
    @staticmethod
    def MergeTagsManagers( tags_managers ):
        
        # we cheat here and just get display tags, since this is read only and storage exacts isn't super important
        
        def CurrentAndPendingFilter( items ):
            
            for ( service_key, statuses_to_tags ) in items:
                
                filtered = { status : tags for ( status, tags ) in list(statuses_to_tags.items()) if status in ( HC.CONTENT_STATUS_CURRENT, HC.CONTENT_STATUS_PENDING ) }
                
                yield ( service_key, filtered )
                
            
        
        # [[( service_key, statuses_to_tags )]]
        s_k_s_t_t_tupled = ( CurrentAndPendingFilter( tags_manager.GetServiceKeysToStatusesToTags( ClientTags.TAG_DISPLAY_ACTUAL ).items() ) for tags_manager in tags_managers )
        
        # [(service_key, statuses_to_tags)]
        flattened_s_k_s_t_t = itertools.chain.from_iterable( s_k_s_t_t_tupled )
        
        # service_key : [ statuses_to_tags ]
        s_k_s_t_t_dict = HydrusData.BuildKeyToListDict( flattened_s_k_s_t_t )
        
        # now let's merge so we have service_key : statuses_to_tags
        
        merged_service_keys_to_statuses_to_tags = collections.defaultdict( HydrusData.default_dict_set )
        
        for ( service_key, several_statuses_to_tags ) in list(s_k_s_t_t_dict.items()):
            
            # [[( status, tags )]]
            s_t_t_tupled = ( list(s_t_t.items()) for s_t_t in several_statuses_to_tags )
            
            # [( status, tags )]
            flattened_s_t_t = itertools.chain.from_iterable( s_t_t_tupled )
            
            statuses_to_tags = HydrusData.default_dict_set()
            
            for ( status, tags ) in flattened_s_t_t:
                
                statuses_to_tags[ status ].update( tags )
                
            
            merged_service_keys_to_statuses_to_tags[ service_key ] = statuses_to_tags
            
        
        return TagsManager( merged_service_keys_to_statuses_to_tags, merged_service_keys_to_statuses_to_tags )
        
    
    def DeletePending( self, service_key ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( ClientTags.TAG_DISPLAY_STORAGE )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            if len( statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] ) + len( statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ] ) > 0:
                
                statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] = set()
                statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ] = set()
                
                self._SetDirty()
                
            
        
    
    def Duplicate( self ):
        
        with self._lock:
            
            dupe_tags_manager = TagsManager( {}, {} )
            
            dupe_tag_display_types_to_service_keys_to_statuses_to_tags = dict()
            
            for ( tag_display_type, service_keys_to_statuses_to_tags ) in self._tag_display_types_to_service_keys_to_statuses_to_tags.items():
                
                dupe_service_keys_to_statuses_to_tags = collections.defaultdict( HydrusData.default_dict_set )
                
                for ( service_key, statuses_to_tags ) in service_keys_to_statuses_to_tags.items():
                    
                    dupe_statuses_to_tags = HydrusData.default_dict_set()
                    
                    for ( status, tags ) in statuses_to_tags.items():
                        
                        dupe_statuses_to_tags[ status ] = set( tags )
                        
                    
                    dupe_service_keys_to_statuses_to_tags[ service_key ] = dupe_statuses_to_tags
                    
                
                dupe_tag_display_types_to_service_keys_to_statuses_to_tags[ tag_display_type ] = dupe_service_keys_to_statuses_to_tags
                
            
            dupe_tags_manager._tag_display_types_to_service_keys_to_statuses_to_tags = dupe_tag_display_types_to_service_keys_to_statuses_to_tags
            dupe_tags_manager._display_cache_is_dirty = self._display_cache_is_dirty
            
            return dupe_tags_manager
            
        
    
    def GetComparableNamespaceSlice( self, service_key: bytes, namespaces: typing.Collection[ str ], tag_display_type: int ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            combined_tags = statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].union( statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] )
            
            pairs = [ HydrusTags.SplitTag( tag ) for tag in combined_tags ]
            
            slice_tags = []
            
            for desired_namespace in namespaces:
                
                subtags = sorted( ( HydrusTags.ConvertTagToSortable( subtag ) for ( namespace, subtag ) in pairs if namespace == desired_namespace ) )
                
                slice_tags.append( tuple( subtags ) )
                
            
            return tuple( slice_tags )
            
        
    
    def GetCurrent( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            return statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ]
            
        
    
    def GetCurrentAndPending( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            return statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].union( statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] )
            
        
    
    def GetDeleted( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            return statuses_to_tags[ HC.CONTENT_STATUS_DELETED ]
            
        
    
    def GetNamespaceSlice( self, service_key: bytes, namespaces: typing.Collection[ str ], tag_display_type: int ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            combined_tags = statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].union( statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] )
            
            namespaces_with_colons = [ '{}:'.format( namespace ) for namespace in namespaces ]
            
            tag_slice = frozenset( ( tag for tag in combined_tags if True in ( tag.startswith( namespace_with_colon ) for namespace_with_colon in namespaces_with_colons ) ) )
            
            return tag_slice
            
        
    
    def GetNumTags( self, tag_context: ClientSearch.TagContext, tag_display_type ):
        
        with self._lock:
            
            num_tags = 0
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ tag_context.service_key ]
            
            if tag_context.include_current_tags: num_tags += len( statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ] )
            if tag_context.include_pending_tags: num_tags += len( statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] )
            
            return num_tags
            
        
    
    def GetPending( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            return statuses_to_tags[ HC.CONTENT_STATUS_PENDING ]
            
        
    
    def GetPetitioned( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            return statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ]
            
        
    
    def GetServiceKeysToStatusesToTags( self, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            return service_keys_to_statuses_to_tags
            
        
    
    def GetStatusesToTags( self, service_key, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            if service_key in service_keys_to_statuses_to_tags:
                
                return service_keys_to_statuses_to_tags[ service_key ]
                
            else:
                
                return collections.defaultdict( set )
                
            
        
    
    def HasTag( self, tag, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            combined_statuses_to_tags = service_keys_to_statuses_to_tags[ CC.COMBINED_TAG_SERVICE_KEY ]
            
            return tag in combined_statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ] or tag in combined_statuses_to_tags[ HC.CONTENT_STATUS_PENDING ]
            
        
    
    def HasAnyOfTheseTags( self, tags, tag_display_type ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( tag_display_type )
            
            combined_statuses_to_tags = service_keys_to_statuses_to_tags[ CC.COMBINED_TAG_SERVICE_KEY ]
            
            return True in ( tag in combined_statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ] or tag in combined_statuses_to_tags[ HC.CONTENT_STATUS_PENDING ] for tag in tags )
            
        
    
    def NewTagDisplayRules( self ):
        
        with self._lock:
            
            self._SetDirty()
            
        
    
    def ProcessContentUpdate( self, service_key, content_update: HydrusData.ContentUpdate ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( ClientTags.TAG_DISPLAY_STORAGE )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            ( data_type, action, row ) = content_update.ToTuple()
            
            ( tag, hashes ) = row
            
            if action == HC.CONTENT_UPDATE_ADD:
                
                statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].add( tag )
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].discard( tag )
                statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_DELETE:
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].add( tag )
                
                statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].discard( tag )
                statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_PEND:
                
                if tag not in statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ]:
                    
                    statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].add( tag )
                    
                
            elif action == HC.CONTENT_UPDATE_RESCIND_PEND:
                
                statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_PETITION:
                
                if tag in statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ]:
                    
                    statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ].add( tag )
                    
                
            elif action == HC.CONTENT_UPDATE_RESCIND_PETITION:
                
                statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_CLEAR_DELETE_RECORD:
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].discard( tag )
                
            
            #
            
            # this does not need to do clever sibling collapse or parent gubbins, because in that case, the db forces tagsmanager refresh
            # so this is just handling things if the content update has no sibling/parent tags
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( ClientTags.TAG_DISPLAY_ACTUAL )
            
            statuses_to_tags = service_keys_to_statuses_to_tags[ service_key ]
            
            ( data_type, action, row ) = content_update.ToTuple()
            
            ( tag, hashes ) = row
            
            if action == HC.CONTENT_UPDATE_ADD:
                
                statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].add( tag )
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].discard( tag )
                statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_DELETE:
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].add( tag )
                
                statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ].discard( tag )
                statuses_to_tags[ HC.CONTENT_STATUS_PETITIONED ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_PEND:
                
                if tag not in statuses_to_tags[ HC.CONTENT_STATUS_CURRENT ]:
                    
                    statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].add( tag )
                    
                
            elif action == HC.CONTENT_UPDATE_RESCIND_PEND:
                
                statuses_to_tags[ HC.CONTENT_STATUS_PENDING ].discard( tag )
                
            elif action == HC.CONTENT_UPDATE_CLEAR_DELETE_RECORD:
                
                statuses_to_tags[ HC.CONTENT_STATUS_DELETED ].discard( tag )
                
            
            #
            
            self._SetDirty()
            
        
    
    def ResetService( self, service_key ):
        
        with self._lock:
            
            service_keys_to_statuses_to_tags = self._GetServiceKeysToStatusesToTags( ClientTags.TAG_DISPLAY_STORAGE )
            
            if service_key in service_keys_to_statuses_to_tags:
                
                del service_keys_to_statuses_to_tags[ service_key ]
                
                self._SetDirty()
                
            
        
    
