import sqlite3
import typing

from hydrus.core import HydrusDB
from hydrus.core import HydrusDBModule
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusTags

from hydrus.client.db import ClientDBMaster

class ClientDBCacheLocalHashes( HydrusDBModule.HydrusDBModule ):
    
    def __init__( self, cursor: sqlite3.Cursor, modules_hashes: ClientDBMaster.ClientDBMasterHashes ):
        
        self.modules_hashes = modules_hashes
        
        self._hash_ids_to_hashes_cache = {}
        
        HydrusDBModule.HydrusDBModule.__init__( self, 'client hashes local cache', cursor )
        
    
    def _GetInitialIndexGenerationTuples( self ):
        
        index_generation_tuples = []
        
        return index_generation_tuples
        
    
    def _PopulateHashIdsToHashesCache( self, hash_ids ):
        
        if len( self._hash_ids_to_hashes_cache ) > 100000:
            
            if not isinstance( hash_ids, set ):
                
                hash_ids = set( hash_ids )
                
            
            self._hash_ids_to_hashes_cache = { hash_id : hash for ( hash_id, hash ) in self._hash_ids_to_hashes_cache.items() if hash_id in hash_ids }
            
        
        uncached_hash_ids = { hash_id for hash_id in hash_ids if hash_id not in self._hash_ids_to_hashes_cache }
        
        if len( uncached_hash_ids ) > 0:
            
            if len( uncached_hash_ids ) == 1:
                
                ( uncached_hash_id, ) = uncached_hash_ids
                
                # this makes 0 or 1 rows, so do fetchall rather than fetchone
                local_uncached_hash_ids_to_hashes = { hash_id : hash for ( hash_id, hash ) in self._Execute( 'SELECT hash_id, hash FROM local_hashes_cache WHERE hash_id = ?;', ( uncached_hash_id, ) ) }
                
            else:
                
                with self._MakeTemporaryIntegerTable( uncached_hash_ids, 'hash_id' ) as temp_table_name:
                    
                    # temp hash_ids to actual hashes
                    local_uncached_hash_ids_to_hashes = { hash_id : hash for ( hash_id, hash ) in self._Execute( 'SELECT hash_id, hash FROM {} CROSS JOIN local_hashes_cache USING ( hash_id );'.format( temp_table_name ) ) }
                    
                
            
            self._hash_ids_to_hashes_cache.update( local_uncached_hash_ids_to_hashes )
            
            uncached_hash_ids = { hash_id for hash_id in uncached_hash_ids if hash_id not in self._hash_ids_to_hashes_cache }
            
        
        if len( uncached_hash_ids ) > 0:
            
            hash_ids_to_hashes = self.modules_hashes.GetHashIdsToHashes( hash_ids = uncached_hash_ids )
            
            self._hash_ids_to_hashes_cache.update( hash_ids_to_hashes )
            
        
    
    def CreateInitialTables( self ):
        
        self._Execute( 'CREATE TABLE IF NOT EXISTS external_caches.local_hashes_cache ( hash_id INTEGER PRIMARY KEY, hash BLOB_BYTES UNIQUE );' )
        
    
    def AddHashIdsToCache( self, hash_ids ):
        
        hash_ids_to_hashes = self.modules_hashes.GetHashIdsToHashes( hash_ids = hash_ids )
        
        self._ExecuteMany( 'INSERT OR IGNORE INTO local_hashes_cache ( hash_id, hash ) VALUES ( ?, ? );', ( ( hash_id, sqlite3.Binary( hash ) ) for ( hash_id, hash ) in hash_ids_to_hashes.items() ) )
        
    
    def ClearCache( self ):
        
        self._Execute( 'DELETE FROM local_hashes_cache;' )
        
    
    def DropHashIdsFromCache( self, hash_ids ):
        
        self._ExecuteMany( 'DELETE FROM local_hashes_cache WHERE hash_id = ?;', ( ( hash_id, ) for hash_id in hash_ids ) )
        
    
    def GetExpectedTableNames( self ) -> typing.Collection[ str ]:
        
        expected_table_names = [
            'external_caches.local_hashes_cache'
        ]
        
        return expected_table_names
        
    
    def GetHash( self, hash_id ) -> str:
        
        self._PopulateHashIdsToHashesCache( ( hash_id, ) )
        
        return self._hash_ids_to_hashes_cache[ hash_id ]
        
    
    def GetHashes( self, hash_ids ) -> typing.List[ bytes ]:
        
        self._PopulateHashIdsToHashesCache( hash_ids )
        
        return [ self._hash_ids_to_hashes_cache[ hash_id ] for hash_id in hash_ids ]
        
    
    def GetHashId( self, hash ) -> int:
        
        result = self._Execute( 'SELECT hash_id FROM local_hashes_cache WHERE hash = ?;', ( sqlite3.Binary( hash ), ) ).fetchone()
        
        if result is None:
            
            return self.modules_hashes.GetHashId( hash )
            
        else:
            
            ( hash_id, ) = result
            
        
        return hash_id
        
    
    def GetHashIds( self, hashes ) -> typing.Set[ int ]:
        
        hash_ids = set()
        hashes_not_in_cache = set()
        
        for hash in hashes:
            
            if hash is None:
                
                continue
                
            
            result = self._Execute( 'SELECT hash_id FROM local_hashes_cache WHERE hash = ?;', ( sqlite3.Binary( hash ), ) ).fetchone()
            
            if result is None:
                
                hashes_not_in_cache.add( hash )
                
            else:
                
                ( hash_id, ) = result
                
                hash_ids.add( hash_id )
                
            
        
        if len( hashes_not_in_cache ) > 0:
            
            hash_ids.update( self.modules_hashes.GetHashIds( hashes_not_in_cache ) )
            
        
        return hash_ids
        
    
    def GetHashIdsToHashes( self, hash_ids = None, hashes = None ) -> typing.Dict[ int, str ]:
        
        if hash_ids is not None:
            
            self._PopulateHashIdsToHashesCache( hash_ids )
            
            hash_ids_to_hashes = { hash_id : self._hash_ids_to_hashes_cache[ hash_id ] for hash_id in hash_ids }
            
        elif hashes is not None:
            
            hash_ids_to_hashes = { self.GetHashId( hash ) : hash for hash in hashes }
            
        
        return hash_ids_to_hashes
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> typing.List[ typing.Tuple[ str, str ] ]:
        
        # we actually provide a backup, which we may want to automate later in mappings caches etc...
        
        return []
        
    
    def HasHashId( self, hash_id: int ):
        
        result = self._Execute( 'SELECT 1 FROM local_hashes_cache WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        return result is not None
        
    
class ClientDBCacheLocalTags( HydrusDBModule.HydrusDBModule ):
    
    def __init__( self, cursor: sqlite3.Cursor, modules_tags: ClientDBMaster.ClientDBMasterTags ):
        
        self.modules_tags = modules_tags
        
        self._tag_ids_to_tags_cache = {}
        
        HydrusDBModule.HydrusDBModule.__init__( self, 'client tags local cache', cursor )
        
    
    def _GetInitialIndexGenerationTuples( self ):
        
        index_generation_tuples = []
        
        return index_generation_tuples
        
    
    def _PopulateTagIdsToTagsCache( self, tag_ids ):
        
        if len( self._tag_ids_to_tags_cache ) > 100000:
            
            if not isinstance( tag_ids, set ):
                
                tag_ids = set( tag_ids )
                
            
            self._tag_ids_to_tags_cache = { tag_id : tag for ( tag_id, tag ) in self._tag_ids_to_tags_cache.items() if tag_id in tag_ids }
            
        
        uncached_tag_ids = { tag_id for tag_id in tag_ids if tag_id not in self._tag_ids_to_tags_cache }
        
        if len( uncached_tag_ids ) > 0:
            
            if len( uncached_tag_ids ) == 1:
                
                ( uncached_tag_id, ) = uncached_tag_ids
                
                # this makes 0 or 1 rows, so do fetchall rather than fetchone
                local_uncached_tag_ids_to_tags = { tag_id : tag for ( tag_id, tag ) in self._Execute( 'SELECT tag_id, tag FROM local_tags_cache WHERE tag_id = ?;', ( uncached_tag_id, ) ) }
                
            else:
                
                with self._MakeTemporaryIntegerTable( uncached_tag_ids, 'tag_id' ) as temp_table_name:
                    
                    # temp tag_ids to actual tags
                    local_uncached_tag_ids_to_tags = { tag_id : tag for ( tag_id, tag ) in self._Execute( 'SELECT tag_id, tag FROM {} CROSS JOIN local_tags_cache USING ( tag_id );'.format( temp_table_name ) ) }
                    
                
            
            self._tag_ids_to_tags_cache.update( local_uncached_tag_ids_to_tags )
            
            uncached_tag_ids = { tag_id for tag_id in uncached_tag_ids if tag_id not in self._tag_ids_to_tags_cache }
            
        
        if len( uncached_tag_ids ) > 0:
            
            tag_ids_to_tags = self.modules_tags.GetTagIdsToTags( tag_ids = uncached_tag_ids )
            
            self._tag_ids_to_tags_cache.update( tag_ids_to_tags )
            
        
    
    def CreateInitialTables( self ):
        
        self._Execute( 'CREATE TABLE IF NOT EXISTS external_caches.local_tags_cache ( tag_id INTEGER PRIMARY KEY, tag TEXT UNIQUE );' )
        
    
    def AddTagIdsToCache( self, tag_ids ):
        
        tag_ids_to_tags = self.modules_tags.GetTagIdsToTags( tag_ids = tag_ids )
        
        self._ExecuteMany( 'INSERT OR IGNORE INTO local_tags_cache ( tag_id, tag ) VALUES ( ?, ? );', tag_ids_to_tags.items() )
        
    
    def ClearCache( self ):
        
        self._Execute( 'DELETE FROM local_tags_cache;' )
        
    
    def DropTagIdsFromCache( self, tag_ids ):
        
        self._ExecuteMany( 'DELETE FROM local_tags_cache WHERE tag_id = ?;', ( ( tag_id, ) for tag_id in tag_ids ) )
        
    
    def GetExpectedTableNames( self ) -> typing.Collection[ str ]:
        
        expected_table_names = [
            'external_caches.local_tags_cache'
        ]
        
        return expected_table_names
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> typing.List[ typing.Tuple[ str, str ] ]:
        
        # we actually provide a backup, which we may want to automate later in mappings caches etc...
        
        return []
        
    
    def GetTag( self, tag_id ) -> str:
        
        self._PopulateTagIdsToTagsCache( ( tag_id, ) )
        
        return self._tag_ids_to_tags_cache[ tag_id ]
        
    
    def GetTagId( self, tag ) -> int:
        
        clean_tag = HydrusTags.CleanTag( tag )
        
        try:
            
            HydrusTags.CheckTagNotEmpty( clean_tag )
            
        except HydrusExceptions.TagSizeException:
            
            raise HydrusExceptions.TagSizeException( '"{}" tag seems not valid--when cleaned, it ends up with zero size!'.format( tag ) )
            
        
        result = self._Execute( 'SELECT tag_id FROM local_tags_cache WHERE tag = ?;', ( tag, ) ).fetchone()
        
        if result is None:
            
            return self.modules_tags.GetTagId( tag )
            
        else:
            
            ( tag_id, ) = result
            
        
        return tag_id
        
    
    def GetTagIdsToTags( self, tag_ids = None, tags = None ) -> typing.Dict[ int, str ]:
        
        if tag_ids is not None:
            
            self._PopulateTagIdsToTagsCache( tag_ids )
            
            tag_ids_to_tags = { tag_id : self._tag_ids_to_tags_cache[ tag_id ] for tag_id in tag_ids }
            
        elif tags is not None:
            
            tag_ids_to_tags = { self.GetTagId( tag ) : tag for tag in tags }
            
        
        return tag_ids_to_tags
        
    
    def UpdateTagInCache( self, tag_id, tag ):
        
        self._Execute( 'UPDATE local_tags_cache SET tag = ? WHERE tag_id = ?;', ( tag, tag_id ) )
        
        if tag_id in self._tag_ids_to_tags_cache:
            
            del self._tag_ids_to_tags_cache[ tag_id ]
            
        
    
